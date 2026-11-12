"""Offline compiler checks: rebuild equivalence and curated-decision guards.

Need SciPy (requirements-economy.txt) and the restored snapshot
(``python -m aoe2x.economy.restore``); otherwise they skip.
"""
import importlib.util
import json
import sqlite3

import pytest

from aoe2x.economy.paths import REVIEW_DB, RUNTIME_DB

pytestmark = [
    pytest.mark.skipif(importlib.util.find_spec("scipy") is None, reason="SciPy is an offline-only dependency"),
    pytest.mark.skipif(not REVIEW_DB.exists(), reason="reviewed snapshot not restored (python -m aoe2x.economy.restore)"),
]


def metadata(path):
    with sqlite3.connect(path) as db:
        return json.loads(db.execute("SELECT payload FROM metadata").fetchone()[0])


@pytest.mark.skipif(not RUNTIME_DB.exists(), reason="runtime database not built")
def test_committed_runtime_is_reproducible(tmp_path):
    from aoe2x.economy.compiler import compile_database
    from aoe2x.economy.paths import REFERENCE_DB
    built = compile_database(REVIEW_DB, REFERENCE_DB, tmp_path / "army_context.db")
    assert built["contextVersion"] == metadata(RUNTIME_DB)["contextVersion"], \
        "data/army_economics/army_context.db is stale: run python -m aoe2x.economy.compiler"


def test_undecided_research_candidate_fails_compilation(monkeypatch):
    from aoe2x.economy import compiler, curated
    decisions = dict(curated.CANDIDATE_DECISIONS)
    decisions.pop(1484)
    monkeypatch.setattr(curated, "CANDIDATE_DECISIONS", decisions)
    with pytest.raises(ValueError, match="needs review"):
        compiler.Compiler(REVIEW_DB, compiler.REFERENCE_DB)


def test_unexpected_prerequisite_activation_fails_compilation(monkeypatch):
    from aoe2x.economy import compiler, curated
    monkeypatch.setattr(curated, "PREREQUISITE_RULE_ACTIVATIONS", set())
    with pytest.raises(ValueError, match="Prerequisite-rule activations"):
        compiler.Compiler(REVIEW_DB, compiler.REFERENCE_DB)
