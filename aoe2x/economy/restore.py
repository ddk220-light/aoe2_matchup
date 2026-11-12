"""Restore the checksummed reviewed source DB and, optionally, the upstream extraction inputs.

    python -m aoe2x.economy.restore                     # army-context.sqlite (compiler input)
    python -m aoe2x.economy.restore --include-sources   # + data/local/army-economics/scratch/...

Every file is verified against the SHA-256 and byte length in the manifest;
identical files are skipped and changed files are never overwritten.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile

from aoe2x.economy.paths import MANIFEST, REPO_ROOT as ROOT


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def destination(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Archive destination escapes checkout: {name}")
    return path


def restore_file(stream, record, root):
    target = destination(root, record["path"])
    if target.exists():
        if sha(target) == record["sha256"]:
            return False
        raise ValueError(f"Refusing to overwrite changed file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".restore.tmp")
    digest = hashlib.sha256()
    size = 0
    try:
        with temporary.open("xb") as output:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(chunk)
                if size > record["bytes"]:
                    raise ValueError(f"Unexpected size for {target}")
                output.write(chunk)
                digest.update(chunk)
        if size != record["bytes"] or digest.hexdigest() != record["sha256"]:
            raise ValueError(f"Restored data does not match manifest: {target}")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-sources", action="store_true", help="Also restore production/research/economy extraction inputs")
    parser.add_argument("--root", type=Path, default=ROOT, help="Destination checkout (defaults to this repository)")
    args = parser.parse_args(argv)
    restored = unchanged = 0
    for archive in json.loads(MANIFEST.read_text())["archives"]:
        if archive["kind"] == "tar-gzip" and not args.include_sources:
            continue
        path = destination(ROOT, archive["archive"])
        if sha(path) != archive["sha256"]:
            raise ValueError(f"Archive checksum mismatch: {path}")
        if archive["kind"] == "gzip-file":
            with gzip.open(path, "rb") as stream:
                changed = restore_file(stream, archive["files"][0], args.root)
                restored += changed
                unchanged += not changed
        elif archive["kind"] == "tar-gzip":
            expected = {r["member"]: r for r in archive["files"]}
            seen = set()
            with tarfile.open(path, "r:gz") as tar:
                for member in tar:
                    if not member.isfile() or member.name not in expected or member.name in seen:
                        raise ValueError(f"Unexpected archive member: {member.name}")
                    seen.add(member.name)
                    with tar.extractfile(member) as stream:
                        changed = restore_file(stream, expected[member.name], args.root)
                        restored += changed
                        unchanged += not changed
            if seen != set(expected):
                raise ValueError(f"Archive is missing files: {path}")
        else:
            raise ValueError(f"Unknown archive format: {archive['kind']}")
        print(f"Verified {archive['archive']}")
    print(f"Restored {restored} files; {unchanged} already matched. Destination: {args.root.resolve()}")


if __name__ == "__main__":
    main()
