"""Committed storage of the compiled army-economics runtime (standard library only).

``data/army_economics/army_context.jsonl.gz`` is the source of truth the site
publishes from. It replaces the 33.6 MB ``army_context.db`` in git; the
compiler still writes that SQLite file as a local, git-ignored build output.

Format (``formatVersion`` 1)::

    gzip (level 9, mtime 0, no file name) of UTF-8 JSON Lines, "\\n" after every line
    line 1   {"format":"aoe2matchup.army-context","formatVersion":1,"metadata":{...}}
    line 2.. {"civ":"Armenians","civilization":{...},"units":[...]}   one line per civilization,
                                                                    sorted by name; units sorted
                                                                    by (unitId, mode)

Every line is canonical JSON (sorted keys, no whitespace, UTF-8, no NaN), the
same encoding the compiler stores in the SQLite payload columns, so payloads are
byte-identical in both forms. The same inputs give the same file bytes with the
same zlib build. ``metadata``/``civilization``/unit payloads are exactly the
compiler's ``metadata``/``civilizations``/``units`` rows (schema:
``aoe2x.economy.accounting.CONTEXT_SCHEMA_VERSION``).

The release step publishes one document per civilization and one metadata
document (``civilization_document`` / ``metadata_document``) through the API
``/api/economy/<civ>`` and ``/api/economy`` and the static ``/data/<version>/``
files. This module is packaged with the backend, so it must not import SciPy,
NumPy or the compiler.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
from pathlib import Path
import re
import sqlite3

FORMAT = "aoe2matchup.army-context"
FORMAT_VERSION = 1
FILE_NAME = "army_context.jsonl.gz"
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "army_economics" / FILE_NAME
_CIV_PREFIX = re.compile(rb'^\{"civ":("(?:[^"\\]|\\.)*"),')


def encode(value):
    """Canonical JSON text (the compiler's payload encoding)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def build(metadata, civilizations, units):
    """Artefact bytes for compiler output: ``civilizations`` maps name -> payload, ``units`` is a list."""
    grouped = {civ: [] for civ in civilizations}
    for unit in units:
        if unit["civ"] not in grouped:
            raise ValueError(f"unit row for unknown civilization: {unit['civ']}")
        grouped[unit["civ"]].append(unit)
    lines = [encode({"format": FORMAT, "formatVersion": FORMAT_VERSION, "metadata": metadata})]
    for civ in sorted(grouped):
        rows = sorted(grouped[civ], key=lambda u: (u["unitId"], u["mode"]))
        if len({(u["unitId"], u["mode"]) for u in rows}) != len(rows):
            raise ValueError(f"duplicate unit rows for {civ}")
        lines.append(encode({"civ": civ, "civilization": civilizations[civ], "units": rows}))
    raw = ("\n".join(lines) + "\n").encode("utf-8")
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, compresslevel=9, mtime=0) as stream:
        stream.write(raw)
    return buffer.getvalue()


def write(path, metadata, civilizations, units):
    path = Path(path)
    data = build(metadata, civilizations, units)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".building")
    temporary.write_bytes(data)
    temporary.replace(path)
    return data


def read_database(path):
    """(metadata, civilizations, units) from a compiled ``army_context.db``."""
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as db:
        metadata = json.loads(db.execute("SELECT payload FROM metadata WHERE id=1").fetchone()[0])
        civilizations = {civ: json.loads(p) for civ, p in db.execute("SELECT civ, payload FROM civilizations")}
        units = [json.loads(p) for (p,) in db.execute("SELECT payload FROM units ORDER BY civ, unit_id, mode")]
    return metadata, civilizations, units


class Artefact:
    """Read-only access; civilization lines are parsed on first use."""

    def __init__(self, path=DEFAULT_PATH):
        self.path = Path(path).resolve()
        if not self.path.exists():
            raise FileNotFoundError(f"Army economics artefact not found: {self.path}")
        lines = gzip.decompress(self.path.read_bytes()).split(b"\n")
        if lines[-1] != b"":
            raise ValueError("Army economics artefact is truncated")
        header = json.loads(lines[0])
        if header.get("format") != FORMAT or header.get("formatVersion") != FORMAT_VERSION:
            raise ValueError("Unsupported army economics artefact format")
        self.metadata = header["metadata"]
        self._lines, self._parsed = {}, {}
        for line in lines[1:-1]:
            match = _CIV_PREFIX.match(line)
            if match is None:
                raise ValueError("Malformed army economics artefact line")
            self._lines[json.loads(match.group(1))] = line
        self.civilizations = sorted(self._lines)
        if self.civilizations != list(self._lines):
            raise ValueError("Army economics artefact civilizations are not sorted")

    def record(self, civ):
        """``{"civ", "civilization", "units"}`` for one civilization; KeyError if unknown."""
        if civ not in self._parsed:
            self._parsed[civ] = json.loads(self._lines[civ])
        return self._parsed[civ]


def civilization_document(artefact, civ):
    """The published per-civilization document (static file and ``/api/economy/<civ>``)."""
    record = artefact.record(civ)
    return {"civ": civ, "civilization": record["civilization"], "units": record["units"],
            "contextVersion": artefact.metadata["contextVersion"],
            "schemaVersion": artefact.metadata["schemaVersion"]}


def metadata_document(artefact):
    """The published metadata document (static ``metadata.json`` and ``/api/economy``)."""
    return {"civilizations": artefact.civilizations, "metadata": artefact.metadata}


def main():
    parser = argparse.ArgumentParser(description="Write the committed artefact from a compiled army_context.db.")
    parser.add_argument("--from-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    data = write(args.output, *read_database(args.from_db))
    print(f"Wrote {args.output} ({len(data):,} bytes)")


if __name__ == "__main__":
    main()
