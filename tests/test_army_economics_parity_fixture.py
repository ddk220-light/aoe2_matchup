"""The committed browser-parity fixture still matches the Python reference.

tests/economy/matchup-parity.test.mjs checks the JS module against the fixture;
this checks the fixture against aoe2x.economy.matchup. On CPython >= 3.12 the
regenerated fixture must be identical; CPython 3.11's plain float sum() differs
in the last bits, so there every 5th pair is compared to 1e-12.
"""
import importlib.util
import json
import sys

import pytest

from aoe2x.economy.paths import REPO_ROOT

spec = importlib.util.spec_from_file_location("parity_fixture", REPO_ROOT / "tools/economy/build_matchup_parity_fixture.py")
fixture_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_tool)


@pytest.mark.skipif(sys.version_info < (3, 12), reason="exact reference needs CPython >= 3.12 float sum()")
def test_fixture_is_current():
    assert fixture_tool.FIXTURE.read_text() == fixture_tool.build(), \
        "stale fixture: run python tools/economy/build_matchup_parity_fixture.py"


def test_fixture_headlines_match_the_reference():
    from aoe2x.economy.matchup import RuntimeData
    fixture = json.loads(fixture_tool.FIXTURE.read_text())
    data = RuntimeData()
    assert fixture["header"]["contextVersion"] == data.metadata["contextVersion"]
    assert len(fixture["cases"]) == fixture["header"]["pairs"] >= 2000
    for expected in fixture["cases"][::5]:
        actual = fixture_tool.expectation(data, {k: expected[k] for k in ("left", "right", "populations")})
        if "error" in expected:
            assert actual["error"] == expected["error"]
            continue
        got, want = actual["summary"], expected["summary"]
        for a, b in zip(got["labor"], want["labor"]):
            assert (a is None) == (b is None) and (a is None or a == pytest.approx(b, rel=1e-12, abs=1e-12))
        assert (got["lowerTeam"], got["production"]) == (want["lowerTeam"], want["production"])
        if sys.version_info >= (3, 12):
            assert actual["sha256"] == expected["sha256"]
