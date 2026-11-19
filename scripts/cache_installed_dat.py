"""Pickle the installed game's parsed DAT for the winter-scenery prepare scripts.

`apps/video/prepare_norse_standard_capture.py` and
`prepare_detailed_standard_capture.py` load
`data/local/viking-sagas-research/installed-dat.pkl`: a genieutils `DatFile`
used to check prop collision sizes. The pickle is ~400 MB and machine-local,
so it is not in Git. Recreate it on a new machine with:

    python scripts/cache_installed_dat.py            # uses AOE2_GAME_DIR
    python scripts/cache_installed_dat.py --dat PATH # explicit .dat

Needs genieutils-py (the conda/video Python that runs aoe2x.extract).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pickle
from pathlib import Path

from genieutils.datfile import DatFile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = r'C:\Program Files (x86)\Steam\steamapps\common\AoE2DE'
OUTPUT = ROOT / 'data/local/viking-sagas-research/installed-dat.pkl'


def main() -> None:
    game = Path(os.environ.get('AOE2_GAME_DIR', DEFAULT_GAME))
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--dat', type=Path, default=game / 'resources/_common/dat/empires2_x2_p1.dat')
    ap.add_argument('--output', type=Path, default=OUTPUT)
    args = ap.parse_args()
    data = args.dat.read_bytes()
    dat = DatFile.parse(str(args.dat))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('wb') as stream:
        pickle.dump(dat, stream, protocol=pickle.HIGHEST_PROTOCOL)
    print(f'{args.output} <- {args.dat} sha256={hashlib.sha256(data).hexdigest()}')


if __name__ == '__main__':
    main()
