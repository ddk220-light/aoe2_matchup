"""Extract a selected streamed WEM from the installed Wwise package, then decode.

AKPK table layout reference:
https://github.com/bnnm/wwiser-utils/blob/master/scripts/wwise_pck_extractor.bms
"""
import argparse
import struct
import subprocess
from pathlib import Path
from overlay.static_stats import GAME


def extract(package, media_id, destination):
    with Path(package).open('rb') as source:
        header = source.read(28)
        if header[:4] != b'AKPK':
            raise ValueError('Expected an AKPK package')
        _, flag, languages, banks, sounds, _ = struct.unpack('<6I', header[4:])
        if flag != 1:
            raise ValueError('Unsupported byte order')
        source.seek(28 + languages + banks)
        table = source.read(sounds)
        count = struct.unpack_from('<I', table)[0]
        if count and (sounds - 4) // count != 20:
            raise ValueError('Unsupported streamed-media table')
        for index in range(count):
            ident, block, size, offset, _ = struct.unpack_from('<5I', table, 4 + index * 20)
            if ident == media_id:
                source.seek(offset * (block or 1))
                data = source.read(size)
                if len(data) != size or data[:4] != b'RIFF':
                    raise ValueError('Invalid WEM data')
                Path(destination).write_bytes(data)
                return
        # Short civilization themes may be embedded in a sound bank instead of
        # the package's streamed-media table (Poles is one such theme). DIDX
        # explicitly maps IDs to byte ranges in DATA; never scan for RIFF bytes
        # or guess an adjacent sound's identity.
        source.seek(28 + languages)
        bank_table = source.read(banks)
        bank_count = struct.unpack_from('<I', bank_table)[0]
        if bank_count and (banks - 4) // bank_count != 20:
            raise ValueError('Unsupported bank table')
        for i in range(bank_count):
            _, block, size, offset, _ = struct.unpack_from('<5I', bank_table, 4 + i * 20)
            source.seek(offset * (block or 1))
            raw = source.read(size)
            data = embedded_media(raw, media_id)
            if data is not None:
                Path(destination).write_bytes(data)
                return
    raise ValueError(f'Media ID {media_id} missing in {package}')


def embedded_media(raw, media_id):
    chunks, cursor = {}, 0
    while cursor + 8 <= len(raw):
        tag, length = struct.unpack_from('<4sI', raw, cursor)
        if cursor + 8 + length > len(raw):
            raise ValueError('Truncated sound bank')
        chunks[tag] = (cursor + 8, length)
        cursor += 8 + length
    if b'DIDX' not in chunks or b'DATA' not in chunks:
        return None
    start, length = chunks[b'DIDX']
    base, available = chunks[b'DATA']
    if length % 12:
        raise ValueError('Invalid embedded-media index')
    for pos in range(start, start + length, 12):
        ident, offset, size = struct.unpack_from('<III', raw, pos)
        if ident != media_id:
            continue
        if offset + size > available:
            raise ValueError('Embedded media extends outside DATA')
        result = raw[base + offset:base + offset + size]
        if result[:4] != b'RIFF':
            raise ValueError('Invalid embedded WEM')
        return result
    return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--decoder', default='.tools/vgmstream/vgmstream-cli.exe')
    parser.add_argument('--media-id', type=int, default=784299781)
    parser.add_argument('--package', type=Path, default=GAME / 'wwise/Base.pck')
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'intro/assets/chinese-theme.wem')
    args = parser.parse_args()
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    extract(args.package, args.media_id, output)
    subprocess.run([args.decoder, '-o', str(output.with_suffix('.wav')), str(output)], check=True)
