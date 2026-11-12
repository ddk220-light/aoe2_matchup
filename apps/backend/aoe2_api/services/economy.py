"""Serve the compiled army-economics runtime: one document per civilization plus metadata.

Reads the committed artefact ``data/army_economics/army_context.jsonl.gz``
(shipped in the packaged runtime). Responses are the canonical bytes the release
step publishes as ``/data/<version>/<civ>.json`` and ``metadata.json``; the pair
calculation runs in the browser (apps/web/src/features/economy/) with
``aoe2x.economy.matchup`` as the Python reference. Never computes anything.
"""
from functools import lru_cache

from aoe2x.economy.artefact import Artefact, FILE_NAME, civilization_document, encode, metadata_document
from aoe2x.paths import DATA_DIR

ARTEFACT = DATA_DIR / 'army_economics' / FILE_NAME


@lru_cache(maxsize=1)
def artefact():
    return Artefact(ARTEFACT)


def economy_civilizations():
    return artefact().civilizations


@lru_cache(maxsize=1)
def economy_metadata():
    """Canonical JSON bytes of the shared metadata document."""
    return encode(metadata_document(artefact())).encode()


@lru_cache(maxsize=56)
def economy_civilization(civilization):
    """Canonical JSON bytes of one civilization's document; LookupError if unknown."""
    if civilization not in artefact().civilizations:
        raise LookupError(civilization)
    return encode(civilization_document(artefact(), civilization)).encode()
