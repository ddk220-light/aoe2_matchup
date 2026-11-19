"""Recorded Hussar screen policy; main-army prices never include the screen."""

import math

BUFFER_POLICY = 'fielded_weighted_cost_v1'
# An empty tile inside both mixed Goldens' existing P4 patrol selection area.
# The original nine records retain their order and positions. The apparent
# diagonal extension at (10.5, 10.5) is a tree, so it must not be used.
EXTRA_HUSSAR_POSITION = (7.5, 5.5)


def hussar_count(army_weighted_cost):
    if (type(army_weighted_cost) not in (int, float)
            or not math.isfinite(army_weighted_cost) or army_weighted_cost <= 0):
        raise ValueError('Invalid fielded army weighted cost')
    return math.floor(max(5, min(10, 5 + (army_weighted_cost - 1000) / 1800)) + .5)


def planned_buffer_positions(source_units, count):
    """Keep first-N Golden slots; permit one explicit extension to ten units."""
    units = list(source_units)
    positions = [(float(u.x), float(u.y), int(u.unit_const)) for u in units]
    if count is None:
        return positions
    if type(count) is not int or not 1 <= count <= 10 or not units:
        raise ValueError('player4_count must be 1..10 with a Golden buffer enabled')
    if count <= len(units):
        return positions[:count]
    if count != 10 or len(units) != 9 or any(u.unit_const != 448 for u in units):
        raise ValueError('player4_count extension requires the nine-scout Golden buffer')
    return positions + [(*EXTRA_HUSSAR_POSITION, 448)]


def validate_scaled_buffer(plan):
    """Independently verify saved scaling against the actual fielded army."""
    scenario = plan['scenario']
    if scenario.get('player4Buffer') != 'scaled':
        if 'player4Scaling' in scenario:
            raise ValueError('Hussar scaling evidence requires scaled buffer mode')
        return
    ranged = [owner for owner in (2, 3) if plan[f'side{owner}']['ranged']]
    if len(ranged) != 1:
        raise ValueError('Scaled buffer requires exactly one ranged side')
    owner = ranged[0]
    family = 'ranged_vs_melee' if owner == 2 else 'melee_vs_ranged'
    side = plan[f'side{owner}']
    cost = sum(side['effectiveCost'][r] * plan['balance']['weights'][r]
               for r in ('food', 'wood', 'gold'))
    total = side['count'] * cost
    count = hussar_count(total)
    expected = dict(policy=BUFFER_POLICY, rangedOwner=owner, fieldedCount=side['count'],
                    weightedUnitCost=cost, armyWeightedCost=total, hussars=count)
    if (scenario['family'] != family or scenario.get('player4Scaling') != expected
            or scenario.get('player4Count') != count or not scenario.get('hasPlayer4Gate')):
        raise ValueError('Hussar buffer does not match the fielded ranged army cost')
