import os
import sys

# Make the API package (apps/backend/aoe2_api) and the aoe2x package importable
# from the repo root — the root is NOT on sys.path when the suite is launched as
# plain `pytest` (e.g. CI) instead of `python -m pytest`. Tests import the API as
# `aoe2_api.web`, never a bare `import app` (apps/backend/app.py is the deployed
# entrypoint and needs the sealed runtime/, which the test job does not build).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "apps", "backend"))
sys.path.insert(0, _ROOT)

import pytest
import aoe2_api.web as flask_app

@pytest.fixture
def client():
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c


@pytest.fixture(scope='session')
def forecast_import_baseline(tmp_path_factory):
    """Restore archived original forecasts in a disposable importer fixture.

    Production can legitimately have zero unreviewed forecasts. Import contracts
    still need original forecasts, available verbatim in the published evidence.
    """
    import json
    from pathlib import Path
    import shutil
    import sqlite3
    import zlib
    source = Path(_ROOT) / 'data/golden/civ_matchups_first_pass.db'
    target = tmp_path_factory.mktemp('forecast-import') / 'baseline.db'
    shutil.copyfile(source, target)
    with sqlite3.connect(target) as db:
        dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
        units = {i: json.loads(data) for i, data in db.execute('SELECT id,data FROM units')}
        for identifier, blob in db.execute('SELECT id,data FROM evidence').fetchall():
            row = json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
            if not row.get('recoveryValidation'):
                continue
            original = row['originalEvidence']
            flags = row['recoveryValidation']['originalCellFlagsAndTiers']
            assert len(flags) == 1
            compressor = zlib.compressobj(9, zdict=dictionary)
            db.execute('UPDATE evidence SET data=? WHERE id=?',
                       (compressor.compress(json.dumps(original).encode()) + compressor.flush(), identifier))
            winner = original['pairKey'].split('|')[0 if original['outcome'] == 'a_win' else 1] if original['outcome'] in ('a_win', 'b_win') else None
            for a, b in db.execute('SELECT a,b FROM cells WHERE evidence_id=?', (identifier,)).fetchall():
                outcome = ('a_win' if units[a]['profileHash'] == winner else 'b_win') if winner else original['outcome']
                db.execute("UPDATE cells SET outcome=?,evidence_type='predicted_unvalidated',flags=?,tier=? WHERE a=? AND b=?",
                           (outcome, flags[0][0], flags[0][1], a, b))
    return target
