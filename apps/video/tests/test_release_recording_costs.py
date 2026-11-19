"""Regression checks against the repository DAT extraction's purchase effects."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'apps/video'))

from prepare_jomsviking_capture import audited_price
import aoe2x.dbgen.unit_analyzer as analyzer_module
from scripts.audit_installed_dat import price as release_audit_price


def test_mayan_initial_tree_discount_precedes_age_discounts(monkeypatch):
    monkeypatch.setattr(analyzer_module, 'OUTPUT_DIR', ROOT / 'data/inputs/extracted_data')
    analyzer = analyzer_module.UnitAnalyzer()
    result = audited_price(analyzer, dict(civ='Mayans', master=765,
        slug='elite_plumed_archer', label='Elite Plumed Archer'))
    assert result['effectiveCost'] == dict(food=0, wood=39, gold=39)
    assert result['effects'][0]['techId'] == 'civ-tree:449'


def test_blackwood_price_is_per_physical_unit(monkeypatch):
    monkeypatch.setattr(analyzer_module, 'OUTPUT_DIR', ROOT / 'data/inputs/extracted_data')
    analyzer = analyzer_module.UnitAnalyzer()
    result = audited_price(analyzer, dict(civ='Tupi', master=2581,
        slug='elite_blackwood_archer_tupi', label='Elite Blackwood Archer'))
    # This fixture is the pre-update 35W/45G purchase; release pricing is 40W/45G.
    assert result['unitsPerPurchase'] == 2
    assert result['effectiveCost'] == dict(food=0, wood=17.5, gold=22.5)


class ConditionalPriceFixture:
    """Isolate the building-count bonus, which has no direct cost command."""
    civ_tech_trees = {}
    effects = {}
    tech_effect_map = {}

    def get_unit(self, master):
        return dict(master=master, **{'class': 6 if master != 2701 else 36})

    def get_base_stats(self, unit):
        costs = (0, 40, 65) if unit['master'] == 2701 else (0, 80, 35) if unit['master'] in (2705, 2706) else (65, 0, 45)
        return SimpleNamespace(**dict(zip(('cost_food', 'cost_wood', 'cost_gold'), costs)))

    def get_disabled_techs(self, *args):
        return set()

    def find_techs_affecting_unit(self, *args):
        return []

    get_civ_bonus_techs_for_unit = find_techs_affecting_unit
    get_unique_techs_for_unit = find_techs_affecting_unit


@pytest.mark.parametrize('civ,master,expected', [
    ('Saxons', 2703, (52, 0, 36)),
    ('Saxons', 2704, (52, 0, 36)),
    ('Saxons', 2706, (0, 64, 28)),
    ('Saxons', 2701, (0, 40, 65)),
    ('Danes', 2704, (65, 0, 45)),
    ('Vikings', 2704, (65, 0, 45)),
    ('Byzantines', 2704, (65, 0, 45)),
    ('Varangians', 2704, (65, 0, 45)),
])
def test_saxon_maximum_foot_discount_in_both_pricing_paths(civ, master, expected):
    analyzer = ConditionalPriceFixture()
    expected = dict(zip(('food', 'wood', 'gold'), expected))
    row = dict(civ=civ, master=master, slug='fixture', label='Fixture')
    assert audited_price(analyzer, row)['effectiveCost'] == expected
    assert release_audit_price(analyzer, civ, master)['cost'] == expected
