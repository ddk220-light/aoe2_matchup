"""Format contract of the committed army-economics artefact (aoe2x/economy/artefact.py). No SciPy."""
import gzip
import json

from aoe2x.economy import artefact
from aoe2x.economy.accounting import CONTEXT_SCHEMA_VERSION
from aoe2x.economy.paths import RUNTIME_ARTEFACT, RUNTIME_DB


def test_committed_artefact_is_canonical_json_lines():
    lines = gzip.decompress(RUNTIME_ARTEFACT.read_bytes()).split(b"\n")
    assert lines[-1] == b""
    header = json.loads(lines[0])
    assert header["format"] == artefact.FORMAT and header["formatVersion"] == artefact.FORMAT_VERSION
    assert header["metadata"]["schemaVersion"] == CONTEXT_SCHEMA_VERSION
    names, total = [], 0
    for line in lines[1:-1]:
        record = json.loads(line)
        assert artefact.encode(record).encode() == line  # canonical: sorted keys, no whitespace
        assert list(record) == ["civ", "civilization", "units"]
        keys = [(u["unitId"], u["mode"]) for u in record["units"]]
        assert keys == sorted(set(keys))
        assert all(u["civ"] == record["civ"] for u in record["units"])
        assert record["civilization"]["civ"] == record["civ"]
        names.append(record["civ"])
        total += len(keys)
    assert names == sorted(names) and len(names) == header["metadata"]["civilizationCount"] == 56
    assert total == header["metadata"]["profileCount"] == 1029


def test_rebuilding_from_the_parsed_content_gives_the_same_lines():
    data = artefact.Artefact(RUNTIME_ARTEFACT)
    civilizations = {c: data.record(c)["civilization"] for c in data.civilizations}
    units = [u for c in reversed(data.civilizations) for u in reversed(data.record(c)["units"])]
    rebuilt = artefact.build(data.metadata, civilizations, units)
    # Byte equality of the gzip stream depends on the zlib build; the compiler
    # test checks it on the build machine. Here: identical content.
    assert gzip.decompress(rebuilt) == gzip.decompress(RUNTIME_ARTEFACT.read_bytes())
    assert gzip.decompress(rebuilt)[:1] == b"{"


def test_documents_and_local_database_agree():
    data = artefact.Artefact(RUNTIME_ARTEFACT)
    meta = artefact.metadata_document(data)
    assert meta["civilizations"] == data.civilizations and meta["metadata"] is data.metadata
    doc = artefact.civilization_document(data, "Wu")
    assert sorted(doc) == ["civ", "civilization", "contextVersion", "schemaVersion", "units"]
    assert doc["contextVersion"] == data.metadata["contextVersion"]
    if RUNTIME_DB.exists():  # local compiler output: same payloads as the artefact
        metadata, civilizations, units = artefact.read_database(RUNTIME_DB)
        assert metadata == data.metadata
        assert civilizations == {c: data.record(c)["civilization"] for c in data.civilizations}
        assert sorted(units, key=lambda u: (u["civ"], u["unitId"], u["mode"])) == \
            [u for c in data.civilizations for u in data.record(c)["units"]]
