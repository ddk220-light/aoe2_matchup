"""Restore a byte-verified immutable public archive into the ignored build cache."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[2]
def restore():
    manifest=json.loads((ROOT/'docs/migration/milestone-3/retained-release.json').read_text())
    target=ROOT/'.migration-cache/retained'/manifest['release_id']
    def valid():
        existing={path.relative_to(target).as_posix() for path in target.rglob('*') if path.is_file()}
        return existing==set(manifest['files']) and all((target/name).is_file() and hashlib.sha256((target/name).read_bytes()).hexdigest()==sha
                   for name,sha in manifest['files'].items())
    if not valid():
        with urlopen(manifest['url'],timeout=30) as response:data=response.read()
        assert hashlib.sha256(data).hexdigest()==manifest['sha256'],'Retained archive hash mismatch'
        with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
            for member in archive:
                assert member.isfile() and member.name in manifest['files'],'Unexpected archive member'
                assert not PurePosixPath(member.name).is_absolute() and '..' not in PurePosixPath(member.name).parts
                file=target/member.name;file.parent.mkdir(parents=True,exist_ok=True)
                file.write_bytes(archive.extractfile(member).read())
        assert valid(),'Retained file hash mismatch'
    return manifest

if __name__=='__main__':
    manifest=restore()
    print(json.dumps({'restored_release':manifest['release_id'],'files':len(manifest['files'])}))
