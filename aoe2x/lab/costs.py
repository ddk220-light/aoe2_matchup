"""Fail closed on legacy, stale, or incorrectly balanced capture plans."""
import hashlib
import json
import math
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[2] / 'data/recording-costs.json'

def validate_plan_costs(plan):
    raw = CATALOG.read_bytes()
    catalog = json.loads(raw)
    balance = plan['balance']
    if balance.get('costBasis') != catalog['costBasis'] or balance.get('costCatalogSha256') != hashlib.sha256(raw).hexdigest():
        raise ValueError('Legacy or stale cost basis: create a new corrected job; never overwrite an archived capture')
    costs = []
    weights = balance['weights']
    for key in ('side2', 'side3'):
        side = plan[key]
        effective = catalog['units'][side['civ']+'|'+side['slug']]['effectiveCost']
        cost = sum(effective[r]*weights[r] for r in weights)
        if side.get('effectiveCost') != effective or side['weightedCost'] != cost or side['armyWeightedResources'] != side['count']*cost:
            raise ValueError('Incorrect effective unit cost or army resource total')
        costs.append(cost)
    if balance['mode'] == 'equal_resources':
        a,b = costs
        if min(a,b) <= 0: raise ValueError('Non-positive weighted cost')
        cap = balance['cap']
        budget = balance.get('maxResources', math.inf)
        n = min(cap, math.floor(budget/min(a,b))) if math.isfinite(budget) else cap
        expected = [n, math.floor(n*a/b)] if a <= b else [math.floor(n*b/a), n]
        if [plan['side2']['count'],plan['side3']['count']] != expected:
            raise ValueError('Army counts do not match effective civilization costs')
    return {'costBasis': catalog['costBasis'], 'costCatalogSha256': balance['costCatalogSha256'], 'verified': True}
