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

API_DIGESTS = {"/api/ref/civ/Spanish": [200, "00594672454a6fb06e75ee7b25f3f322506ce4396d6f237a34ac03f3457db741"], "/api/ref/combat-unit/Spanish/champion": [200, "9db1a26a508f642f9755d0e483ba9f0f52717e2a8642312f2f656bce9b40bf82"], "/api/ref/unit-line/infantry": [200, "155361ae66462a85e8794dd6bc067e75765fed60d9f8d4c91a7adddcdee55bc4"], "/api/ref/unit-line/archery": [200, "b7a0c3db25e220165d9fad74de2407370fa6105b224571fef973ac20c6a41757"], "/api/ref/unit-line/stable": [200, "7253c9540977837ca2530e5c5361767777e90b19a84bd9aaf3a05c14fc6009c2"], "/api/v3/arena-preview": [200, "6b4eb89cc0d536e0165ff4dd243889d6d74457d67a54d02aeb032d797b12b63d"]}

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
    assert hashlib.sha256(json.dumps(configs, sort_keys=True).encode()).hexdigest() == '60a0716209cf3b9ab4ef966ed0163a73f1b4e97102a8cff7a048b96f82d19c25'
    result = subprocess.run(['node', 'aoe2x/js_simulation/node/headless-runner.mjs', '--workers', '2'], cwd=ROOT, input=json.dumps(configs), text=True, capture_output=True, check=True, timeout=90)
    rows = json.loads(result.stdout)['results']
    assert tuple((r['eventLogHash'], r['finalStateHash']) for r in rows) == (('7fe60c84927b0404809005af7367d5891efa771b378e6d598187844ed9933436', '26698860ebfe6610b32188bf74ca2b8fb5ef244f60672287d03e2e056c2d9719'), ('a0f870ec2555ba9e957b89d321f166e2f0ae8f93a728e28ebf64d0f6ec537b4f', 'a9011d0124c71b239bb867800295f0d015851ac17c70941b7a36336ba1e50eed'), ('05bd83f4f692bcb0b4efd43015cdcbe0451d3de0bc78d1da21e235a6b8e5d8f8', '7c0017c626063eb087d2f57c48b931a4e25c9e7ce17b9f6e60de5e94ddbe8d79'), ('9546d7a0451ac282f3f79747f663db0238b3a116497a1d8d59782df631c6b644', 'd868247711b3c6a913b9d916d7d0af088e8b3e5b47290a953947743c8ff1e4d2'), ('8f2277033c7ea56aaa648c7e24971be2d5681304dc4ed2544533a92adf7a30f3', '7d48ad9d623c644453169e5b46c7f8f10e13c12e6451d47013b069e0bbc2d5fb'))
