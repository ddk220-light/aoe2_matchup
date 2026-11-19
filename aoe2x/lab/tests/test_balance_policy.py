"""The approved default must reach every new-plan entry point and public copy."""

from aoe2x.lab.balance import DEFAULT_BALANCE, DEFAULT_COMPARISON_POLICY, DEFAULT_RESOURCE_WEIGHTS, balance_caption, balance_description
from aoe2x.lab.cli import _normalize_batch_row, build_parser
from aoe2x.lab.planner import make_request


def test_new_cli_python_and_batch_requests_use_geometric():
    assert make_request(side2="a", side3="b")["balance"]["mode"] == DEFAULT_BALANCE
    assert make_request(side2="a", side3="b")["balance"]["weights"] == DEFAULT_RESOURCE_WEIGHTS
    args = build_parser().parse_args(["plan", "--side2", "a", "--side3", "b"])
    assert (args.food_weight, args.wood_weight, args.gold_weight) == (1, .9, 1.1)
    assert (
        build_parser().parse_args(["plan", "--side2", "a", "--side3", "b"]).balance
        == DEFAULT_BALANCE
    )
    row = {"side2": "a", "side3": "b"}
    assert _normalize_batch_row(row, {})["balance"]["mode"] == DEFAULT_BALANCE
    assert _normalize_batch_row(row, {})["balance"]["weights"] == DEFAULT_RESOURCE_WEIGHTS
    assert make_request(side2="a", side3="b", wood_weight=1, gold_weight=1)["balance"]["weights"] == {"food":1,"wood":1,"gold":1}
    row["balance"] = {"mode": "equal_resources"}
    assert _normalize_batch_row(row, {})["balance"]["mode"] == "equal_resources"


def test_public_copy_follows_saved_policy_not_current_default():
    old = {"balance": {"mode": "equal_resources", "cap": 27}}
    new = {"balance": {"mode": DEFAULT_BALANCE, "cap": 27}}
    assert "Equal resources" in balance_caption(old)
    assert "Equal resources" in balance_description(old)
    assert "Equal resources" not in balance_caption(new)
    assert "geometric mean" in balance_description(new)
    assert "half strength" in balance_description(new)
    assert "gold discounts count in full" in balance_description(new)


def test_unit_population_policy_copy_preserves_historical_descriptions():
    historical = {'balance': {'mode': DEFAULT_BALANCE, 'cap': 27, 'comparisonPolicy': 'geometric_shared_discount_v1'}}
    current = {'balance': {'mode': DEFAULT_BALANCE, 'cap': 27, 'comparisonPolicy': DEFAULT_COMPARISON_POLICY}}
    assert 'Cost + population' in balance_caption(historical)
    assert 'population efficiency' in balance_description(historical)
    assert 'Geometric cost balance' in balance_caption(current)
    assert 'every physical unit as one population' in balance_description(current)
    assert 'population efficiency' not in balance_description(current)
    assert 'All civilization discounts count in full' in balance_description(current)
    assert 'food 1, wood 0.9, gold 1.1' in balance_description(current)
    v2 = {'balance': {'mode': DEFAULT_BALANCE, 'cap': 27, 'comparisonPolicy': 'geometric_shared_discount_unit_count_v2'}}
    assert 'Geometric cost balance' in balance_caption(v2)
    assert 'every physical unit as one population' in balance_description(v2)
    assert 'half strength' in balance_description(v2)
    assert 'wood 0.9' not in balance_description(v2)


def test_node_plan_passes_independent_python_cost_validation():
    import json
    import shutil
    import subprocess
    from pathlib import Path
    import pytest
    from aoe2x.lab.costs import validate_plan_costs

    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is required for the cross-runtime planning check')
    root = Path(__file__).resolve().parents[3]
    request = make_request(side2='elite_champi_warrior_incas', side3='paladin', civ3='Spanish')
    result = subprocess.run([node, str(root/'aoe2x/js_simulation/tools/aoe2lab_worker.mjs'), 'plan'],
                            input=json.dumps(request), capture_output=True, text=True, check=True, cwd=root)
    plan = json.loads(result.stdout)
    assert [plan[s]['count'] for s in ('side2','side3')] == [27,18]
    assert validate_plan_costs(plan)['verified']
