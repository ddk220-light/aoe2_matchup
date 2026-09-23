from apps.website.services.battles import _v3_counts
from aoe2x.js_simulation.scenario_config import build_scenario_payload
from pathlib import Path
import app as website


def team(food=0, wood=0, gold=0):
    return {"mechanics": {"cost": dict(food=food, wood=wood, gold=gold)}}


def test_default_uses_geometric_cost_counts_not_equal_spend():
    assert _v3_counts({}, [team(food=100), team(food=225)], (27, 27)) == (27, 18)
    assert _v3_counts({}, [team(wood=100), team(gold=100)], (27, 27)) == (27, 24)


def test_manual_counts_remain_exact():
    teams = [{**team(food=100), "count": 7}, {**team(food=225), "count": 19}]
    assert _v3_counts({"mode": "explicit"}, teams, (27, 27)) == (7, 19)


def test_dynamic_buffer_uses_first_slots_and_new_tenth_slot():
    scenario = build_scenario_payload("ranged_vs_melee", engine_family="kite",
                                      include_buffer=True, player4_count=10)
    cells = scenario["auxiliaryArmiesByOwner"]["4"]["cells"]
    assert len(cells) == 10
    assert cells[-1] == {"x": 7.5, "y": 5.5}
    smaller = build_scenario_payload("ranged_vs_melee", engine_family="kite",
                                    include_buffer=True, player4_count=5)
    assert smaller["auxiliaryArmiesByOwner"]["4"]["cells"] == cells[:5]


def test_new_civilizations_are_selectable_without_replacing_ranking_reference(client, monkeypatch):
    candidate = Path(__file__).resolve().parents[1] / "data/local/generated/patch-185872/aoe2_reference.db"
    monkeypatch.setattr(website, "SIM_REF_DB_PATH", str(candidate), raising=False)
    old_reference = website.REF_DB_PATH
    for civ, slug in [("Saxons", "elite_hearth_troop_saxons"), ("Varangians", "elite_jarl_varangians"),
                      ("Danes", "elite_jomsviking_danes")]:
        response = client.get(f"/api/ref/civ/{civ}")
        assert response.status_code == 200
        assert any(u["unit_slug"] == slug for u in response.json["units_by_age"]["Imperial"])
        combat = client.get(f"/api/ref/combat-unit/{civ}/{slug}")
        assert combat.status_code == 200
        assert combat.json["mechanics"]["civilization"] == civ
    assert website.REF_DB_PATH == old_reference
