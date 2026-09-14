"""Resolve simple campaign Event -> Play Action -> Sound references in Wwise v154.

Strictly supports the direct sound events used by Wei/Art of War. It does not
walk parent buses or guess media IDs from arbitrary bank bytes.
"""
import argparse
import json
import struct
import subprocess
from pathlib import Path
from extract_intro_music import extract
from overlay.static_stats import GAME


def fnv1(name):
    value = 2166136261
    for byte in name.lower().encode():
        value = ((value * 16777619) & 0xffffffff) ^ byte
    return value


def banks(package):
    with package.open('rb') as source:
        header = source.read(28)
        _, flag, languages, size, _, _ = struct.unpack('<6I', header[4:])
        if header[:4] != b'AKPK' or flag != 1:
            raise ValueError('Unsupported package')
        source.seek(28 + languages)
        table = source.read(size)
        count = struct.unpack_from('<I', table)[0]
        if count and (size - 4) // count != 20:
            raise ValueError('Unsupported bank table')
        for i in range(count):
            ident, block, length, offset, _ = struct.unpack_from('<5I', table, 4 + 20*i)
            source.seek(offset * (block or 1))
            yield ident, source.read(length)


def objects(data):
    result = {}
    position = 0
    while position + 8 <= len(data):
        tag, length = struct.unpack_from('<4sI', data, position)
        if tag == b'BKHD' and struct.unpack_from('<I', data, position+8)[0] != 154:
            raise ValueError('Only Wwise bank v154 is supported')
        if tag == b'HIRC':
            cursor = position + 12
            while cursor < position + 8 + length:
                kind, size, ident = struct.unpack_from('<BII', data, cursor)
                result[ident] = (kind, data[cursor+9:cursor+5+size])
                cursor += 5 + size
        position += 8 + length
    return result


def resolve(event, output, decoder):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    packages = list((GAME/'wwise/en').glob('*.pck'))
    event_id = fnv1(event)
    for package in packages:
        for bank_id, raw in banks(package):
            entries = objects(raw)
            if event_id not in entries:
                continue
            kind, data = entries[event_id]
            if kind != 4 or data[0] != 1:
                raise ValueError('Expected a single-action event')
            action_id = struct.unpack_from('<I', data, 1)[0]
            kind, action = entries[action_id]
            if kind != 3 or action[:2] != b'\x03\x04':
                raise ValueError('Expected a direct Play action')
            sound_id = struct.unpack_from('<I', action, 2)[0]
            kind, sound = entries[sound_id]
            if kind != 2 or sound[:5] != b'\x01\x00\x14\x00\x01':
                raise ValueError('Expected a streamed Wwise Opus sound')
            media_id = struct.unpack_from('<I', sound, 5)[0]
            for media_package in packages:
                try:
                    extract(media_package, media_id, output/f'{event}.wem')
                except ValueError:
                    continue
                subprocess.run([decoder, '-o', str(output/f'{event}.wav'),
                                str(output/f'{event}.wem')], check=True)
                record = {'event': event, 'eventId': event_id, 'actionId': action_id,
                          'soundId': sound_id, 'mediaId': media_id,
                          'bankId': bank_id, 'bankPackage': str(package),
                          'mediaPackage': str(media_package)}
                (output/f'{event}.json').write_text(json.dumps(record, indent=2))
                return record
            raise ValueError('Resolved media ID was not found')
    raise ValueError('Campaign event was not found')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--event', default='PLAY_WEI1S1')
    p.add_argument('--output', default='.tools/intro-voice')
    p.add_argument('--decoder', default='.tools/vgmstream/vgmstream-cli.exe')
    a = p.parse_args()
    print(json.dumps(resolve(a.event, a.output, a.decoder), indent=2))
