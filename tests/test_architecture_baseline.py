"""Pre-refactor serving contracts; update only with a reviewed data/engine release."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/website'))
import app as web

API_DIGESTS = {"/api/ref/civ/Spanish":[200,"be8997ef6f4480976f505c4d5279990619e694fd743326b3135af6bbbfdf5558"],"/api/ref/combat-unit/Spanish/champion":[200,"9d181800d6a9b985b322113e87e263df427258b1d29668bcef3409edd5bd4694"],"/api/ref/unit-line/infantry":[200,"25611c0322e493766234671f367f8c2376219694fbc346b3f3169b8fb537880e"],"/api/ref/unit-line/archery":[200,"b7896d08a4dedcfb09c5e063128c4a57736fab1cc98613067943ca6c5f7ddeac"],"/api/ref/unit-line/stable":[200,"cc78d6674340061ef1841d67786f3a893cfc4e72b748e04d8375f6045d612467"],"/api/v3/arena-preview":[200,"6b4eb89cc0d536e0165ff4dd243889d6d74457d67a54d02aeb032d797b12b63d"]}

@pytest.mark.parametrize('path,expected', API_DIGESTS.items())
def test_preserved_api_payload(path, expected):
    response = web.app.test_client().get(path)
    digest = hashlib.sha256(json.dumps(response.get_json(), sort_keys=True).encode()).hexdigest()
    assert [response.status_code, digest] == expected

def test_preserved_v3_battle_panel():
    if not shutil.which('node'):
        pytest.skip('Node required for the active V3 contract')
    pairs = [('Spanish','champion','Spanish','paladin'), ('Chinese','arbalester','Spanish','hand_cannoneer'), ('Chinese','heavy_scorpion','Chinese','arbalester'), ('Bulgarians','elite_konnik_bulgarians','Spanish','paladin'), ('Chinese','arbalester','Spanish','paladin')]
    client = web.app.test_client()
    configs = []
    for i, (ca, ua, cb, ub) in enumerate(pairs):
        response = client.post('/api/v3/battle-config', json={'teams':[{'civ':ca,'unit_slug':ua,'count':2},{'civ':cb,'unit_slug':ub,'count':2}], 'army':{'mode':'explicit'}, 'seed':100+i, 'engagement_mode':'ranged_buffer' if i==4 else 'direct'})
        assert response.status_code == 200
        configs.append(response.get_json())
    assert hashlib.sha256(json.dumps(configs, sort_keys=True).encode()).hexdigest() == '7fc8b936023a3cb2cece5fc204159c14e15cbfde8f1702851cbc5dfc9b635c15'
    result = subprocess.run(['node', 'aoe2x/js_simulation/node/headless-runner.mjs', '--workers', '2'], cwd=ROOT, input=json.dumps(configs), text=True, capture_output=True, check=True, timeout=90)
    rows = json.loads(result.stdout)['results']
    assert tuple((r['eventLogHash'], r['finalStateHash']) for r in rows) == (("7fe60c84927b0404809005af7367d5891efa771b378e6d598187844ed9933436","9f3428ce062f16c0d713455a8fcf62ad537c43995f1ae39216d89a58d01b8217"),("a0f870ec2555ba9e957b89d321f166e2f0ae8f93a728e28ebf64d0f6ec537b4f","627a36337df49ac1c673e2ea9e74688982fa054a093cd28e936f79ee9303af0a"),("05bd83f4f692bcb0b4efd43015cdcbe0451d3de0bc78d1da21e235a6b8e5d8f8","8e96cf7e80ca3ed35ca88c253914cc62fea19985f19bb830214651a193148bdd"),("9546d7a0451ac282f3f79747f663db0238b3a116497a1d8d59782df631c6b644","f9b339a042484d3c04d8ed2cdcd409601367d895df44c6d98789bcc62d31567f"),("8f2277033c7ea56aaa648c7e24971be2d5681304dc4ed2544533a92adf7a30f3","3a606d36d63a01d8ab8509a2af159be09aa9792804145fbf9fa96e6666a17b5f"))
