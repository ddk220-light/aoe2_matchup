"""Contract of the compiled runtime database (data/army_economics/army_context.db).

Ported from matchup-timings 829c65bec ``tests/test_army_economics.py``. The
former page/API tests (``apps.website`` ArmyContext, Flask endpoint, battle
count resolution and combat-trajectory replay of the cost overlay) are not
ported: that UI/API was deleted and integration is an owner-led next step.
Per-pair accounting now goes through ``aoe2x.economy.matchup``.
"""
import json
import os
from pathlib import Path
import sqlite3

import pytest

from aoe2x.economy.accounting import add_costs, compiled_labor, weighted_cost
from aoe2x.economy.paths import REFERENCE_DB, RUNTIME_DB

RUNTIME = Path(os.environ.get("ARMY_CONTEXT_DB", RUNTIME_DB))
pytestmark = pytest.mark.skipif(not RUNTIME.exists(), reason="army_context.db not built")
needs_scipy = pytest.mark.skipif(__import__("importlib").util.find_spec("scipy") is None,
                                 reason="SciPy (requirements-economy.txt) is an offline-only dependency")


@pytest.fixture(scope="module")
def data():
    from aoe2x.economy.matchup import RuntimeData
    return RuntimeData(RUNTIME)


def pair(data, left, right=None, count=27):
    from aoe2x.economy.matchup import evaluate_matchup
    def sel(x):
        civ, uid, *mode = x
        return (civ, uid, mode[0] if mode else "default", count)
    return evaluate_matchup(data, sel(left), sel(right or left))


def civ(name):
    with sqlite3.connect(RUNTIME) as c:
        return json.loads(c.execute("SELECT payload FROM civilizations WHERE civ=?", (name,)).fetchone()[0])


def units(where="1=1", args=()):
    with sqlite3.connect(RUNTIME) as c:
        return [json.loads(r[0]) for r in c.execute(f"SELECT payload FROM units WHERE {where}", args)]


def test_actual_profile_coverage_and_source_join(data):
    with sqlite3.connect(REFERENCE_DB) as c:
        c.row_factory = sqlite3.Row
        profiles = c.execute("SELECT m.mode, m.mechanics_json, u.civ_name FROM ref_unit_mechanics m "
                             "JOIN ref_units u ON u.id=m.ref_unit_id").fetchall()
    keys = set(data.keys())
    for profile in profiles:
        uid = json.loads(profile["mechanics_json"])["unit_master"]
        if (profile["civ_name"], uid, profile["mode"]) not in keys:
            continue  # rows dropped by an explicit owner decision (see test_dropped_roster_rows)
        unit = data.unit(profile["civ_name"], uid, profile["mode"])
        assert len(unit["lookup"]) == 28
        assert unit["lookup"][0]["trainingSeconds"] == 0
        assert unit["lookup"][0]["labor"]["seconds"] == 0
        assert unit["lookup"][0]["weightedLabor"]["seconds"] == 0
        if unit["production"]["status"] == "modeled":
            assert unit["production"]["trainingSeconds"] <= 60
            assert unit["production"]["buildingCount"] > 0
            for entry in unit["lookup"]:
                if entry["weightedLabor"] is not None:
                    assert entry["weightedLabor"]["seconds"] >= entry["labor"]["seconds"] - 1e-8
    assert len(profiles) == 1031
    assert data.metadata["profileCount"] == len(keys)


@pytest.mark.parametrize("civ_name,uid,building", [("Huns", 757, "Stable"), ("Goths", 555, "Barracks"),
                                                 ("Bulgarians", 1227, "Krepost"), ("Spanish", 42, "Castle")])
def test_training_routes(data, civ_name, uid, building):
    u = pair(data, (civ_name, uid))["teams"][0]
    assert u["production"]["name"] == building
    if civ_name == "Huns":
        assert 483 in {t["id"] for t in u["research"]["military"]["technologies"]}
    if civ_name == "Goths":
        assert 16 in {t["id"] for t in u["research"]["military"]["technologies"]}


def test_alternate_forms(data):
    u = pair(data, ("Bengalis", 1740))["teams"][0]
    assert u["production"]["trainedUnitId"] == 1761
    assert u["production"]["formIdentity"]["displayUnitId"] == 1740
    u = pair(data, ("Shu", 1980, "barrage"))["teams"][0]
    assert (u["unitId"], u["sourceUnitId"]) == (1980, 1962)


def test_batch_and_conditional_cost_policies(data):
    u = pair(data, ("Tupi", 2581))["teams"][0]
    assert u["startingArmy"]["orders"] == 14
    assert u["startingArmy"]["surplusUnits"] == 1
    assert u["pricing"]["physicalUnitCost"]["wood"] == 20
    losses = u["replacementLookup"]
    assert losses[1]["initialSurplusUsed"] == 1
    assert losses[1]["weightedLabor"]["seconds"] == 0
    assert losses[1]["orders"] == 0
    assert losses[2]["orders"] == losses[3]["orders"] == 1
    assert losses[2]["surplusUnits"] == 1
    assert losses[3]["surplusUnits"] == 0
    assert losses[4]["orders"] == 2
    discounted = [u for u in units("civ='Saxons'") if u["pricing"]["conditionalMultiplier"] == .8]
    assert len(discounted) == 6
    assert all(u["pricing"]["conditionalContext"] for u in discounted)


def test_verified_price_corrections(data):
    for civ_name, uid, expected in [("Magyars", 871, {"food": 80, "wood": 0, "gold": 0}),
                                    ("Mapuche", 2571, {"food": 0, "wood": 43, "gold": 47}),
                                    ("Mayans", 492, {"food": 0, "wood": 18, "gold": 32}),
                                    ("Mayans", 765, {"food": 0, "wood": 39, "gold": 39})]:
        cost = data.unit(civ_name, uid)["pricing"]["physicalUnitCost"]
        assert {r: cost[r] for r in expected} == expected
    corrected = {(p["civ"], p["unitId"]) for p in data.metadata["priceCorrections"]}
    assert {("Magyars", 871), ("Mapuche", 2571), ("Mayans", 492), ("Mayans", 765)} <= corrected


def test_food_army_includes_farm_woodcutters(data):
    u = pair(data, ("Spanish", 441))["teams"][0]  # Hussar: food-only unit bill.
    assert u["startingArmy"]["cost"]["wood"] == 0
    assert u["startingArmy"]["labor"]["workByActivity"]["wood"] > 0
    assert u["startingArmy"]["weightedLabor"]["seconds"] == pytest.approx(u["startingArmy"]["labor"]["seconds"])


def test_free_upgrades_refunds_and_persian_work_rates(data):
    vikings = {t["id"]: t for t in civ("Vikings")["technologies"]}
    assert vikings[213]["seconds"] == 0  # Wheelbarrow
    assert not any(vikings[213]["upfront"].values())
    persians = {t["id"]: t for t in civ("Persians")["technologies"]}
    assert persians[213]["seconds"] == pytest.approx(62.5)
    ts = pair(data, ("Spanish", 567))["teams"][0]["research"]["military"]["technologies"]
    assert any(t["refund"]["gold"] == 20 for t in ts)
    assert all(t["net"]["gold"] == pytest.approx(t["upfront"]["gold"] - t["refund"]["gold"]) for t in ts)


def test_flemish_population_is_explicit_and_does_not_poison_cache(data):
    from aoe2x.economy.matchup import evaluate_matchup
    sel = ("Burgundians", 1699, "default", 27)
    def f(response):
        return next(t for t in response["teams"][0]["research"]["military"]["technologies"] if t["id"] == 755)
    base = f(evaluate_matchup(data, sel, sel))
    variable = f(evaluate_matchup(data, sel, sel, [50, None]))
    assert base["upfront"]["food"] == 200
    assert variable["upfront"]["food"] == 700
    assert f(evaluate_matchup(data, sel, sel)) == base
    for invalid in ([True, None], [-1, None], [1.5, None]):
        with pytest.raises(ValueError):
            evaluate_matchup(data, sel, sel, invalid)


def test_pasture_estimate_and_release_gate_are_honest(data):
    u = pair(data, ("Khitans", 567))["teams"][0]
    assert u["startingArmy"]["labor"] is not None
    assert not u["economy"]["blockers"]
    assert u["investment"]["labor"] is not None
    assert u["economy"]["pastureModel"]["foodPerVillagerMinute"] == pytest.approx(25.2)
    assert data.metadata["releaseReady"]
    assert data.metadata["gatheringValidation"]["status"] == "deferred_by_user"


def test_previous_schema_is_rejected(tmp_path):
    from aoe2x.economy.matchup import RuntimeData
    old = tmp_path / "old-context.db"
    with sqlite3.connect(old) as db:
        db.execute("CREATE TABLE metadata (id INTEGER PRIMARY KEY, payload TEXT)")
        db.execute("INSERT INTO metadata VALUES(1, ?)", (json.dumps({"schemaVersion": 2}),))
    with pytest.raises(ValueError, match="Unsupported army context schema"):
        RuntimeData(old)


@needs_scipy
@pytest.mark.parametrize("left,right,buildings", [
    (("Spanish", 567), ("Saracens", 492), [3, 4]),
    (("Spanish", 567), ("Saracens", 567), [3, 3]),
    (("Chinese", 492), ("Saracens", 492), [4, 4]),
])
def test_investment_uses_only_common_techs_and_correct_infrastructure(data, left, right, buildings):
    from aoe2x.economy.accounting import solve_labor
    response = pair(data, left, right, count=7)
    for i, team in enumerate(response["teams"]):
        common = response["researchComparison"]["common"][i]
        score = team["investment"]
        assert score["components"]["commonResearch"] == common["net"]
        assert score["cost"] == add_costs(team["startingArmy"]["cost"], team["production"]["investmentCost"], common["net"])
        assert score["labor"]["seconds"] == pytest.approx(
            solve_labor(weighted_cost(score["cost"]), team["economy"]["activities"])["seconds"])
        assert team["startingArmy"]["trainingSeconds"] <= 60
        assert team["replacementLookup"][0]["weightedLabor"]["seconds"] == 0
        assert all(b["alreadyAvailable"] == (b["id"] == team["production"]["id"])
                   for b in team["research"]["allInfrastructure"]["buildings"])
    if left[1] == right[1]:
        assert response["researchComparison"]["common"][0]["technologyCount"] > 0
        if left[0] == "Spanish":
            assert response["researchComparison"]["common"][0]["refund"]["gold"] > 0
        if left[0] == "Chinese":
            assert sum(response["researchComparison"]["common"][0]["upfront"].values()) < \
                sum(response["researchComparison"]["common"][1]["upfront"].values())
    else:
        assert response["researchComparison"]["exclusive"][0]["technologyCount"] > 0
    assert [t["production"]["buildingCount"] for t in response["teams"]] == buildings
    a = pair(data, left, left, count=7)
    assert a["investmentComparison"]["lowerTeam"] is None


@needs_scipy
def test_all_compiled_economies_match_offline_solver():
    from aoe2x.economy.accounting import solve_labor
    with sqlite3.connect(RUNTIME) as db:
        economies = [json.loads(r[0]) for r in db.execute("SELECT payload FROM civilizations")]
    for economy in economies:
        if economy["blockers"]:
            assert economy["laborPrices"] is None
            continue
        for cost in ({"food": 800, "wood": 600, "gold": 1000, "stone": 1950},
                     {"food": 80}, {"food": 200, "gold": -40}, {"wood": 200, "stone": 350}):
            bill = weighted_cost(cost)
            assert compiled_labor(bill, economy["laborPrices"])["seconds"] == pytest.approx(
                solve_labor(bill, economy["activities"])["seconds"])


def test_explicit_scope_exceptions_do_not_pretend_validation(data):
    excluded = data.metadata["scopeExceptions"]
    # Owner decision 8 (2026-11-12): Xebec and Chinese Fire Ship rows are dropped, not waived.
    assert {(r["civ"], r.get("unitId"), r.get("technologyId")) for r in excluded} == {
        ("Wei", None, 1061), ("Burgundians", None, 755)}
    assert all(r["status"] == "excluded_by_user" for r in excluded)
    assert data.metadata["blockers"] == []
    assert data.metadata["gatheringValidation"]["status"] == "deferred_by_user"
    response = pair(data, ("Wei", 441))
    assert response["teams"][0]["investment"]["labor"] is not None
    economy = response["teams"][0]["economy"]
    assert not economy["blockers"]
    assert economy["scopeExceptions"][0]["technologyId"] == 1061
    effect = next(e for e in economy["effects"] if e["technologyId"] == 1061)
    assert effect["calculationStatus"] == "excluded_by_user"
    assert response["auraAssumption"]["coverage"] == 1
    assert response["auraAssumption"]["placementRequired"] is False
    assert response["auraAssumption"]["infrastructureCostIncluded"] is False
    assert response["releaseReady"]
    assert response["status"] == "estimate"


def test_pasture_animals_and_herders_are_independent_source_parameters(data):
    source = pair(data, ("Khitans", 567))["teams"][0]["economy"]["pastureSourceInputs"]
    assert source["food"] == 1035
    assert source["animalCount"] == 9
    assert source["herderCount"] == 2
    assert source["actors"]["1892"]["roundedCarry"] == 6
    assert source["actors"]["1889"]["cost"]["wood"] == 110
    assert {e["technologyId"] for e in source["evidence"]} == {1012, 1013, 1014}
    assert source["status"] == "online_reference_estimate"


def test_scope_waivers_are_narrow():
    from aoe2x.economy.policy import exclusion_reason
    assert exclusion_reason({"code": "unresolved_economy_mechanic", "civ": "Wei", "technologyId": 1061})
    assert exclusion_reason({"code": "unresolved_economy_mechanic", "civ": "Wei", "technologyId": 9999}) is None
    assert exclusion_reason({"code": "controlled_observations_missing"}) is None
    assert exclusion_reason({"code": "unresolved_training_route", "civ": "Chinese", "unitId": 492}) is None


@pytest.mark.parametrize("civ_name,resource,kind", [
    ("Burgundians", "food", "gold_per_active_gathering_minute"),
    ("Vietnamese", "wood", "gold_per_active_gathering_minute"),
    ("Georgians", "food", "worker_work_rate_aura"),
    ("Malians", "gold", "extra_dropoff_credit"),
    ("Poles", "stone", "coproduct"), ("Shu", "wood", "coproduct"),
])
def test_resolved_special_economies_reach_runtime_without_claiming_validation(data, civ_name, resource, kind):
    economy = civ(civ_name)
    assert not economy["blockers"]
    assert economy["laborPrices"]
    activity = next(a for a in economy["activities"] if a["id"] == resource)
    mechanic = next(m for m in activity["appliedMechanics"] if m["kind"] == kind)
    assert mechanic["technologyIds"]
    assert activity["status"] == "scenario_estimate"
    assert data.metadata["releaseReady"]
    assert data.metadata["gatheringValidation"]["status"] != "validated"
    if kind == "gold_per_active_gathering_minute":
        assert 0 < activity["outputs"]["gold"] < mechanic["value"] / 60
    if resource == "food":
        assert activity["outputs"]["wood"] < 0


def test_research_summary_reports_common_exclusive_and_full(data):
    response = pair(data, ("Franks", 569), ("Japanese", 359))
    for i, team in enumerate(response["teams"]):
        s = team["researchSummary"]
        assert s["inHeadline"] == "common"
        assert s["common"]["technologyCount"] + s["exclusive"]["technologyCount"] == s["full"]["technologyCount"]
        for r in ("food", "wood", "gold", "stone"):
            assert s["common"]["net"][r] + s["exclusive"]["net"][r] == pytest.approx(s["full"]["net"][r])
        assert s["common"]["workloadSeconds"] + s["exclusive"]["workloadSeconds"] == pytest.approx(s["full"]["workloadSeconds"])
        assert s["full"]["villagerMinutes"] > 0
        assert s["exclusive"]["villagerMinutes"] > 0
        assert team["investment"]["components"]["commonResearch"] == s["common"]["net"]


# ---------------------------------------------------------------------------
# Owner decisions and review fixes of 2026-11-12 (aoe2x/economy/curated.py).

def techs(unit, package="military"):
    return {t["id"]: t for t in unit["research"][package]["technologies"]}


def test_dropped_roster_rows(data):
    keys = set(data.keys())
    assert ("Berbers", 1631, "default") not in keys and ("Chinese", 529, "default") not in keys
    assert {(d["civ"], d["unitId"]) for d in data.metadata["droppedProfiles"]} == {("Berbers", 1631), ("Chinese", 529)}
    assert data.metadata["profileCount"] == 1029 == len(keys)


@pytest.mark.parametrize("civ_name,uid,tid,net,seconds", [
    ("Poles", 1707, 786, {"food": 300, "gold": 800}, 45.11),
    ("Lithuanians", 1707, 786, {"food": 600, "gold": 800}, 45.11),
    ("Danes", 567, 1484, {"food": 250, "gold": 450}, 26.32), ("Danes", 359, 1484, None, None),
    ("Danes", 2712, 1484, None, None), ("Danes", 2704, 1484, None, None),
    ("Saxons", 567, 1464, {"food": 525, "gold": 475}, 33.83), ("Saxons", 359, 1464, None, None),
    ("Saxons", 2706, 1464, None, None), ("Saxons", 2704, 1464, None, None),
    ("Khitans", 441, 1007, {"food": 600, "gold": 300}, 33.83), ("Khitans", 1372, 1007, None, None),
    ("Khitans", 330, 1007, None, None),
    ("Shu", 359, 1070, {"food": 350, "gold": 300}, 30.08), ("Shu", 1961, 1070, None, None),
    ("Mapuche", 2568, 1380, {"food": 500, "gold": 450}, 33.83),
    ("Wu", 528, 1080, {"food": 400, "gold": 250}, 30.08),
])
def test_missing_technologies_added(data, civ_name, uid, tid, net, seconds):
    t = techs(data.unit(civ_name, uid))[tid]
    if net:
        assert {r: t["net"][r] for r in net} == net
        assert t["seconds"] == pytest.approx(seconds, abs=0.01)


@pytest.mark.parametrize("civ_name,uid,tid", [("Khitans", 474, 1007), ("Khitans", 1923, 1007)])
def test_projectile_cavalry_do_not_get_ordo_cavalry(data, civ_name, uid, tid):
    assert tid not in techs(data.unit(civ_name, uid))


@pytest.mark.parametrize("civ_name,uid,tid", [("Teutons", 567, 11), ("Teutons", 359, 11), ("Teutons", 554, 11),
                                              ("Georgians", 283, 924), ("Georgians", 441, 924),
                                              ("Georgians", 474, 924), ("Georgians", 1805, 924)])
def test_non_combat_research_removed(data, civ_name, uid, tid):
    unit = data.unit(civ_name, uid)
    assert tid not in techs(unit) and tid not in techs(unit, "production")
    assert tid in {t["id"] for t in unit["research"]["excludedNonCombat"]}


def test_every_flagged_research_candidate_has_a_decision(data):
    review = {r["technologyId"]: r for r in data.metadata["researchCandidateReview"]}
    assert {1484, 1464, 1007, 1070, 1380, 1080} <= {t for t, r in review.items() if r["decision"] == "added"}
    assert all(r["reason"] for r in review.values())


def test_production_fixes(data):
    priest = data.unit("Armenians", 1811)
    assert priest["production"]["name"] == "Fortified Church"
    assert priest["production"]["cost"]["wood"] == 200
    for uid, building in ((359, "Barracks"), (6, "Archery Range")):
        unit = data.unit("Mapuche", uid)
        assert unit["production"]["name"] == building
        assert unit["production"]["secondsPerOrder"] == pytest.approx(16.541, abs=1e-3)
        assert "SETTL1" in {r["name"] for r in unit["productionRoutes"]}
    assert data.unit("Persians", 442)["production"]["secondsPerOrder"] == pytest.approx(22.5, abs=1e-4)
    for unit in units():
        names = {r["name"] for r in unit["productionRoutes"]}
        assert unit["civ"] == "Sicilians" or "Donjon" not in names
    assert "Donjon" in {r["name"] for r in data.unit("Sicilians", 359)["productionRoutes"]}


def test_mapuche_line_upgrades_research_at_the_regular_building(data):
    assert techs(data.unit("Mapuche", 6))[98]["building"]["name"] == "Archery Range"
    assert techs(data.unit("Mapuche", 6))[98]["seconds"] == pytest.approx(37.594, abs=1e-3)
    assert techs(data.unit("Mapuche", 359))[429]["seconds"] == pytest.approx(37.594, abs=1e-3)


def test_price_corrections_and_half_up_rounding(data):
    assert data.unit("Mapuche", 2568)["pricing"]["physicalUnitCost"] == {"food": 55, "wood": 0, "gold": 34, "stone": 0}
    assert data.unit("Gurjaras", 875)["pricing"]["physicalUnitCost"]["food"] == 53   # 52.5
    assert data.unit("Koreans", 359)["pricing"]["physicalUnitCost"]["wood"] == 13    # 12.5
    assert data.unit("Koreans", 6)["pricing"]["physicalUnitCost"]["wood"] == 18      # 17.5 (unchanged)


def test_wu_production_buildings_are_charged_net_of_the_food_grant(data):
    unit = data.unit("Wu", 359)
    p = unit["production"]
    assert p["completionRebate"]["food"] == 55
    assert p["investmentCost"]["food"] == -55 * p["buildingCount"]
    assert p["grossInvestmentCost"]["wood"] == 175 * p["buildingCount"]
    assert data.unit("Wu", 1970)["production"]["completionRebate"] is None  # Castle: no grant
    assert data.unit("Chinese", 359)["production"]["completionRebate"] is None


def test_danes_food_dropoff_and_poles_steady_state(data):
    danes = next(a for a in civ("Danes")["activities"] if a["id"] == "food")
    assert danes["outputs"]["food"] * 60 == pytest.approx(24.71, abs=0.01)
    assert -danes["outputs"]["wood"] / danes["outputs"]["food"] == pytest.approx(0.1524, abs=1e-3)
    mechanic = next(m for m in danes["appliedMechanics"] if m["kind"] == "extra_dropoff_credit")
    assert mechanic["creditPercent"] == 5 and mechanic["technologyIds"] == [1494]
    poles = next(a for a in civ("Poles")["activities"] if a["id"] == "food")
    assert poles["outputs"]["food"] * 60 == pytest.approx(25.71, abs=0.01)
    assert poles["appliedMechanics"][0]["kind"] == "steady_state_window"


def test_notes_and_assumptions_are_recorded(data):
    assert "-15%" in civ("Italians")["notes"]["ageUp"]["text"]
    assert civ("Byzantines")["notes"]["ageUp"]["datModifiers"]
    assert civ("Ethiopians")["notes"]["ageUp"]["source"].startswith("aoe2techtree")
    assert civ("Franks")["notes"]["ageUp"] is None
    assert any("4 relics" in n for n in civ("Lithuanians")["notes"]["civilization"])
    assert any("four controlled" in n for n in civ("Saxons")["notes"]["civilization"])
    assert any("lowest-confidence" in n for n in civ("Khitans")["notes"]["civilization"])
    assert "Feitoria" in civ("Portuguese")["notes"]["excludedIncome"]
    assert "Caravanserai" in data.metadata["excludedIncome"]
    assert data.metadata["gatheringValidationPolicy"]["status"] == "deferred_by_user"
    assert all(a["status"] in ("scenario_estimate", "online_reference_estimate")
               for e in map(civ, ("Khitans", "Danes", "Poles")) for a in e["activities"])


def test_every_unit_carries_its_full_research_package_figures(data):
    for unit in units():
        s = unit["research"]["military"]["summary"]
        assert s["technologyCount"] == unit["research"]["military"]["totals"]["technologyCount"]
        if s["technologyCount"] and s["costIsFixed"] and s["weightedCost"] > 0:
            assert s["villagerMinutes"] > 0
