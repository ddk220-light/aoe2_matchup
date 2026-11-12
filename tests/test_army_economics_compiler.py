"""Offline compiler checks: rebuild equivalence and curated-decision guards.

Need SciPy (requirements-economy.txt) and the restored snapshot
(``python -m aoe2x.economy.restore``); otherwise they skip.
"""
import importlib.util

import pytest

from aoe2x.economy.paths import REVIEW_DB

pytestmark = [
    pytest.mark.skipif(importlib.util.find_spec("scipy") is None, reason="SciPy is an offline-only dependency"),
    pytest.mark.skipif(not REVIEW_DB.exists(), reason="reviewed snapshot not restored (python -m aoe2x.economy.restore)"),
]


def test_committed_runtime_is_reproducible(tmp_path):
    """Rebuilding gives the committed artefact byte for byte (and a matching local SQLite runtime)."""
    from aoe2x.economy.artefact import Artefact, read_database
    from aoe2x.economy.compiler import compile_database
    from aoe2x.economy.paths import REFERENCE_DB, RUNTIME_ARTEFACT
    built = compile_database(REVIEW_DB, REFERENCE_DB, tmp_path / "army_context.db",
                             artefact=tmp_path / "army_context.jsonl.gz")
    assert built["contextVersion"] == Artefact(RUNTIME_ARTEFACT).metadata["contextVersion"], \
        "data/army_economics/army_context.jsonl.gz is stale: run python -m aoe2x.economy.compiler"
    assert (tmp_path / "army_context.jsonl.gz").read_bytes() == RUNTIME_ARTEFACT.read_bytes()
    metadata, civilizations, units = read_database(tmp_path / "army_context.db")
    committed = Artefact(RUNTIME_ARTEFACT)
    assert metadata == committed.metadata
    assert {c: committed.record(c)["civilization"] for c in committed.civilizations} == civilizations
    assert len(units) == sum(len(committed.record(c)["units"]) for c in committed.civilizations)


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
