"""The approved default must reach every new-plan entry point and public copy."""

from aoe2x.lab.balance import DEFAULT_BALANCE, balance_caption, balance_description
from aoe2x.lab.cli import _normalize_batch_row, build_parser
from aoe2x.lab.planner import make_request


def test_new_cli_python_and_batch_requests_use_geometric():
    assert make_request(side2="a", side3="b")["balance"]["mode"] == DEFAULT_BALANCE
    assert (
        build_parser().parse_args(["plan", "--side2", "a", "--side3", "b"]).balance
        == DEFAULT_BALANCE
    )
    row = {"side2": "a", "side3": "b"}
    assert _normalize_batch_row(row, {})["balance"]["mode"] == DEFAULT_BALANCE
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
