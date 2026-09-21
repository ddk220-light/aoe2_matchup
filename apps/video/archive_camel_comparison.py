"""Compact completed camel recordings using the verified archive pipeline.

The destination must already exist. Existing conflicting files are never
overwritten; local media is pruned only after verified replacement and receipts.
"""
import argparse
from pathlib import Path

import archive_champi_geometric as archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    archive.DEST = args.destination.resolve(strict=True)
    archive.JOB_PREFIX = 'camel_'
    archive.ARCHIVE_PREFIX = 'camel-comparison'
    archive.TITLE_PREFIX = 'Camel Comparison'
    archive.PRESERVE_BASELINE = False
    for folder, civs in (
        ('camel-comparison', ('hindustanis', 'gurjaras', 'berbers', 'byzantines',
                              'ethiopians', 'saracens', 'khitans', 'malians')),
        ('camel-baseline', ('turks',)),
    ):
        archive.OUT = archive.ROOT / 'data/local' / folder
        archive.CIVS = civs
        print(f'Archiving {folder} to {archive.DEST}', flush=True)
        archive.main()


if __name__ == '__main__':
    main()
