"""Build the four-civilization Champi spike from the owner's immutable layout.

This is deliberately separate from the production two-player Golden contract.
The rounded most-expensive pair is the reference; cheaper variants scale that
opponent HP pool, retaining full units plus at most one partly injured unit.
This is an HP handicap experiment, not exact equality of purchase resources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / 'apps/video/templates/comp4_goldens/comp_4_no_buffer.aoe2scenario'
GOLDEN_SHA = 'c38252f1f99a156ae97247b685268e804c9b7e4395491b06b84b1f34b4723753'
CIVS = ['Incas', 'Mapuche', 'Muisca', 'Tupi']


def hp_roster(reference_cost, variant_cost, opponent_cost, opponent_hp, cap=8):
    """Keep the reference subject count; discount its integer opponent baseline.

    Fractions prevent floating-point errors from inventing a near-zero last
    unit. HP is rounded only once, at the final partial unit (integer trigger).
    """
    ref, variant, other = map(Fraction, (reference_cost, variant_cost, opponent_cost))
    if not (0 < variant <= ref and other > 0 and opponent_hp > 0 and cap > 0):
        raise ValueError('Invalid costs, HP or cap')
    subjects, opponents = (cap, int(cap * ref / other)) if ref <= other else (int(cap * other / ref), cap)
    if min(subjects, opponents) < 1:
        raise ValueError('Reference costs cannot fit both sides under the cap')
    target = opponents * variant / ref
    whole = int(target)
    partial = round((target - whole) * opponent_hp)
    hps = [opponent_hp] * whole + ([partial] if partial else [])
    if not hps:
        raise ValueError('Discount removes the complete opponent army')
    return {'subjectCount': subjects, 'referenceOpponentCount': opponents,
            'costRatio': float(variant / ref), 'opponentEquivalentUnits': float(target),
            'opponentHP': hps, 'opponentTotalHP': sum(hps)}


def audited_costs():
    """Use the same installed-DAT effects and rounding as the corrected recorder."""
    import aoe2x.dbgen.unit_analyzer as module
    extracted = ROOT / 'data/local/cost-audit-extracted'
    catalog = json.loads((ROOT / 'data/recording-costs.json').read_text())
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in extracted.glob('*.json')}
    if not hashes or hashes != catalog['extractionHashes']:
        raise ValueError('Cost extraction differs from the audited recording catalog')
    module.OUTPUT_DIR = extracted
    analyzer = module.UnitAnalyzer()
    rows = []
    for civ, master in [(c, 2554) for c in CIVS] + [('Armenians', 1802)]:
        unit = analyzer.get_unit(master)
        stats = analyzer.get_base_stats(unit)
        resources = ['food', 'wood', 'gold']
        base = {r: getattr(stats, 'cost_' + r) for r in resources}
        disabled = analyzer.get_disabled_techs(civ)
        stages = [analyzer.tech_effect_map[t] for t in sorted(analyzer.find_techs_affecting_unit(master, unit['class'], 4))
                  if t not in disabled and t in analyzer.tech_effect_map]
        stages += analyzer.get_civ_bonus_techs_for_unit(civ, master, unit['class'], 4)
        stages += analyzer.get_unique_techs_for_unit(civ, master, unit['class'], 4)
        effects = []
        for tech in stages:
            for cmd in tech.get('commands', []):
                if cmd.get('c') not in (100, 103, 104, 105):
                    continue
                before = {r: getattr(stats, 'cost_' + r) for r in resources}
                analyzer.apply_effect_command(cmd, stats, master, unit['class'])
                after = {r: getattr(stats, 'cost_' + r) for r in resources}
                if before != after:
                    effects.append({'techId': tech['tech_id'], 'before': before, 'after': after})
        final = {r: round(getattr(stats, 'cost_' + r)) for r in resources}
        rows.append({'civ': civ, 'master': master, 'base': base, 'final': final,
                     'total': sum(final.values()), 'unitsPerPurchase': 1, 'effects': effects})
    return rows, hashes


def generate(output: Path, opponent=None, *, cached_costs=None, quiet=False):
    from AoE2ScenarioParser import settings
    from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
    settings.PRINT_STATUS_UPDATES = False
    if hashlib.sha256(GOLDEN.read_bytes()).hexdigest() != GOLDEN_SHA:
        raise ValueError('Golden hash mismatch')
    if output.resolve() == GOLDEN.resolve():
        raise ValueError('Never overwrite the Golden')
    if output.exists():
        raise FileExistsError(output)
    from AoE2ScenarioParser.datasets.object_support import Civilization
    costs, hashes = cached_costs or audited_costs()
    costs = list(costs)
    opponent_master, opponent_hp, opponent_civ = 1800, 50, 'Armenians'
    opponent_label = 'Elite Composite Bowman'
    if opponent is not None:
        opponent_master, opponent_hp, opponent_civ = opponent['master'], opponent['hp'], opponent['civ']
        opponent_label = opponent['label']
        costs[4] = opponent['costEvidence']
    reference = max(r['total'] for r in costs[:4])
    opponent_cost = costs[4]['total']
    sc = AoE2DEScenario.from_file(str(GOLDEN))
    starting = sc.trigger_manager.triggers[0]
    original_effects = list(starting.effects)
    injuries = []
    pairs = []
    for owner, cost in enumerate(costs[:4], 1):
        rival = owner + 4
        plan = hp_roster(reference, cost['total'], opponent_cost, opponent_hp)
        sc.player_manager.players[rival].civilization = Civilization[opponent_civ.upper().replace(' ', '_')]
        own_units = [u for u in sc.unit_manager.get_player_units(owner) if u.unit_const == 2554]
        rival_units = [u for u in sc.unit_manager.get_player_units(rival) if u.unit_const == 1800]
        assert len(own_units) == len(rival_units) == 8
        slots = []
        for units, hps in [(own_units, [None] * plan['subjectCount']), (rival_units, plan['opponentHP'])]:
            for idx, unit in enumerate(units):
                if idx >= len(hps):
                    sc.unit_manager.remove_unit(unit=unit)
                    continue
                if units is rival_units:
                    unit.unit_const = opponent_master
                slots.append({'owner': owner if units is own_units else rival, 'referenceId': unit.reference_id,
                              'x': unit.x, 'y': unit.y, 'rotation': unit.rotation, 'initialHP': hps[idx]})
                if hps[idx] is not None and hps[idx] < opponent_hp:
                    # Damage changes current HP, leaving the unit's maximum HP and
                    # combat attributes untouched. Execute before any patrol order.
                    adjustment=(opponent or {}).get('runtimeAdjustment',{})
                    compensation=adjustment.get('injuryCompensation',0)
                    if compensation and len(hps)!=adjustment['injuredArmyCount']:
                        raise ValueError('Runtime injury compensation was not validated for this army size')
                    effect = starting.new_effect.damage_object(source_player=rival,
                        selected_object_ids=[unit.reference_id], quantity=opponent_hp-hps[idx]+compensation)
                    injuries.append(effect)
        pairs.append({'subjectOwner': owner, 'opponentOwner': rival, 'civ': cost['civ'],
                      'subjectCost': cost['total'], 'opponentCost': opponent_cost, **plan, 'slots': slots})
    starting.effects = injuries + original_effects
    output.parent.mkdir(parents=True, exist_ok=True)
    sc.write_to_file(str(output))
    reopened = AoE2DEScenario.from_file(str(output))
    for pair in pairs:
        for owner, master, count in [(pair['subjectOwner'], 2554, pair['subjectCount']),
                                     (pair['opponentOwner'], opponent_master, len(pair['opponentHP']))]:
            units = [u for u in reopened.unit_manager.get_player_units(owner) if u.unit_const == master]
            expected = [s for s in pair['slots'] if s['owner'] == owner]
            assert len(units) == count
            assert [(u.reference_id, u.x, u.y, u.rotation) for u in units] == [
                (s['referenceId'], s['x'], s['y'], s['rotation']) for s in expected]
    manifest = {'schemaVersion': 1, 'mode': 'comp4_reference_baseline_fractional_opponent_hp',
        'golden': str(GOLDEN.relative_to(ROOT)), 'goldenSha256': GOLDEN_SHA,
        'scenario': str(output), 'scenarioSha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'subjectMaster': 2554, 'placedOpponentMaster': opponent_master, 'expectedGrpcOpponentMaster': opponent_master,
        'opponent': {'label':opponent_label, 'civ':opponent_civ, 'master':opponent_master, 'hp':opponent_hp},
        'subjectHP': {'1':65,'2':80,'3':65,'4':65},
        'runtimeAdjustment': (opponent or {}).get('runtimeAdjustment'),
        'runtimeIdentityNote': 'Verify the placed master and actual starting HP independently.',
        'maxUnitsPerOwner': 8, 'costBasis': 'fully_upgraded_imperial_v1',
        'description': 'Integer reference counts first; discount scales the reference opponent HP pool. Not exact purchase-cost equality.',
        'costs': costs, 'extractionHashes': hashes, 'pairs': pairs,
        'runtimeValidation': 'PENDING: verify Post-Imperial upgrades, starting HP and four independent results in game'}
    output.with_suffix('.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    if not quiet:
        print(json.dumps({'scenario': str(output), 'pairs': [{k:v for k,v in p.items() if k != 'slots'} for p in pairs]}, indent=2))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    generate(parser.parse_args().output)
