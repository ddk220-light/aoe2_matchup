"""Matchup rerun tooling (aoe2x/matchups): hashes, army counts, configs, inventory, engine pin.

Runs without the research branch (RB); RB-dependent acceptance checks are CLI
commands (replay-check, check-inventory-2026, import-results) that skip
cleanly when RB is missing, which the last test asserts.
"""
import copy
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from aoe2x.matchups import artifacts
from aoe2x.matchups import battle as BT
from aoe2x.matchups import bundle as B
from aoe2x.matchups import config as C
from aoe2x.matchups import engine as E
from aoe2x.matchups import inventory as I
from aoe2x.matchups.canonical import canonical_json, digest, js_number, key2, profile_hash
from aoe2x.matchups.cli import load_inputs
from aoe2x.matchups.paths import CONFIGS_DIR, REPO_ROOT

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "matchups"
NODE = shutil.which("node")


@pytest.fixture(scope="module")
def bundle():
    return B.load_bundle(artifacts.CAMPAIGN_2026_BUNDLE)


@pytest.fixture(scope="module")
def full_config():
    return json.loads((CONFIGS_DIR / "full-2026-reproduction.json").read_text())


# ------------------------------------------------------------------- hashing

@pytest.mark.parametrize("value,text", [
    (1, "1"), (1.0, "1"), (-0.0, "0"), (0.5, "0.5"), (22.5, "22.5"), (1e-7, "1e-7"), (1.5e-5, "0.000015"),
    (1e21, "1e+21"), (1e20, "100000000000000000000"), (0.1 + 0.2, "0.30000000000000004"),
    (5e-324, "5e-324"), (1.7976931348623157e308, "1.7976931348623157e+308"), (123456789.125, "123456789.125"),
])
def test_js_number_matches_json_stringify(value, text):
    assert js_number(value) == text


def test_canonical_json_sorts_keys_without_whitespace():
    assert canonical_json({"b": [1, 2.0, None], "a": {"y": True, "x": "é"}}) == '{"a":{"x":"é","y":true},"b":[1,2,null]}'


def test_profile_hash_ignores_only_civilization(bundle):
    v = bundle["variants"][0]
    m = copy.deepcopy(v["mechanics"])
    assert profile_hash(m) == v["profileHash"]
    assert digest(m) == v["mechanicsHash"]
    m["civilization"] = "Somewhere Else"
    assert profile_hash(m) == v["profileHash"]
    m["hp"] += 1
    assert profile_hash(m) != v["profileHash"]
    assert key2("b", "a") == "a|b" == key2("a", "b")


def test_committed_bundle_is_the_2026_definition(bundle):
    s = B.summarize_bundle(bundle)
    assert (s["variants"], s["profiles"], s["civilizations"], s["excluded"]) == (555, 374, 56, 475)
    assert s["groups"] == {"Cavalry": 134, "Infantry": 147, "Ranged": 274}
    assert bundle["game"]["referenceDbSha256"].startswith("234ad0a6")
    assert bundle["source"]["campaignHash"] == B.FROZEN_2026_CAMPAIGN_HASH
    assert artifacts.CAMPAIGN_2026_BUNDLE.stat().st_size < 1_000_000


# --------------------------------------------------------------- army counts

def test_army_count_formula():
    # Pilot example: Armenian Halberdier (57.5) vs Armenian Paladin (142.5) -> [27, 17].
    assert BT.army_counts(57.5, 142.5) == (27, 17)
    assert BT.army_counts(142.5, 57.5) == (17, 27)
    assert BT.army_counts(72, 72) == (27, 27)
    assert BT.army_counts(1, 10_000_000) == (27, 1)  # never below one unit
    assert BT.army_counts(57.5, 142.5, cap=20) == (20, 13)
    assert BT.js_round(2.5) == 3 and BT.js_round(3.5) == 4  # Math.round, not banker's rounding
    assert BT.weighted_cost({"food": 60, "wood": 0, "gold": 75}) == 60 + 1.1 * 75
    assert BT.policy_text({"armyCap": 27, "resourceWeights": BT.DEFAULT_WEIGHTS, "disableAiOrders": True,
                           "disableKiting": True, "preserveOwnerOrientation": True}) == \
        "27-geometric-cost-v3; zero buffers; disableAiOrders; disableKiting; preserveOwnerOrientation"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_army_counts_match_the_pinned_engine(bundle):
    costs = sorted({json.dumps(v["mechanics"]["cost"], sort_keys=True) for v in bundle["variants"]})
    costs = [json.loads(c) for c in costs]
    classes = ["melee", "mobile_ranged", "siege_ranged"]
    cases = [[a, b, classes[i % 3], classes[(i // 3) % 3]] for i, (a, b) in
             enumerate((a, b) for a in costs for b in costs[::7])]
    setup = (E.engine_dir() / "aoe2x/js_simulation/src/battle-setup.js").as_uri()
    script = (f"import {{deriveRecordedBattleSetup as d}} from {json.dumps(setup)};"
              "import {readFileSync} from 'node:fs';"
              "const cases=JSON.parse(readFileSync(0,'utf8'));"
              "console.log(JSON.stringify(cases.map(([a,b,c2,c3])=>{const s=d({class:c2,effectiveCost:a},"
              "{class:c3,effectiveCost:b},{cap:27});return [s.n2,s.n3,s.cost2,s.cost3];})));")
    out = subprocess.run([NODE, "--input-type=module", "-e", script], input=json.dumps(cases),
                         capture_output=True, text=True, check=True)
    engine = json.loads(out.stdout)
    for (a, b, _, _), (n2, n3, c2, c3) in zip(cases, engine):
        w2, w3 = BT.weighted_cost(a), BT.weighted_cost(b)
        assert (w2, w3) == (c2, c3)
        assert BT.army_counts(w2, w3) == (n2, n3)
    assert len(cases) > 500


# ------------------------------------------------------------------- configs

@pytest.mark.parametrize("name", sorted(p.stem for p in CONFIGS_DIR.glob("*.json")))
def test_example_configs_validate(name):
    cfg = C.load(CONFIGS_DIR / f"{name}.json")
    assert cfg["runId"]
    assert not str(C.records_dir(cfg)).startswith(str(REPO_ROOT))


@pytest.mark.parametrize("mutate,message", [
    (lambda c: c.update(extra=1), "unknown top-level"),
    (lambda c: c.update(schema="v0"), "schema must be"),
    (lambda c: c.update(runId="bad id"), "runId"),
    (lambda c: c["game"].pop("bundleHash"), "bundleHash"),
    (lambda c: c["game"].update(referenceDb="x.db"), "exactly one"),
    (lambda c: c["battle"].update(armyCap=40), "armyCap"),
    (lambda c: c["battle"].update(armyCap=True), "armyCap"),
    (lambda c: c["battle"].update(bufferUnits=5), "bufferUnits"),
    (lambda c: c["battle"].update(resourceWeights={"food": 1, "wood": 1}), "resourceWeights"),
    (lambda c: c["battle"].update(orientation={"rule": "random"}), "orientation"),
    (lambda c: c["battle"].update(unknownFlag=True), "battle: unknown"),
    (lambda c: c["engine"].update(nodeVersionPolicy="loose"), "nodeVersionPolicy"),
    (lambda c: c["engine"].update(wallTimeoutSteps=[600, 180]), "wallTimeoutSteps"),
    (lambda c: c["engine"].update(environment={"PATH": "/bin"}), "AOE2X_EXP_"),
    (lambda c: c["sampling"].update(initialSeeds=[0, 0, 1]), "distinct"),
    (lambda c: c["sampling"].update(policy="ml-forecast"), "sampling.policy"),
    (lambda c: c["selection"].update(mode="incremental"), "baselineResults"),
    (lambda c: c["selection"].update(civilizations=[]), "selection.civilizations"),
    (lambda c: c.update(output={"records": "data/runs/x"}), "inside the repository"),
    (lambda c: c.update(roster={"rule": "ranking-roster-v1"}), "roster rules apply only"),
])
def test_invalid_configs_are_rejected(full_config, mutate, message):
    raw = copy.deepcopy(full_config)
    mutate(raw)
    with pytest.raises(C.ConfigError, match=message):
        C.validate(raw)


def test_config_hash_and_setup_hash_change_with_conditions(full_config):
    base = C.validate(full_config)
    other = copy.deepcopy(full_config)
    other["battle"]["armyCap"] = 20
    changed = C.validate(other)
    engine = E.load_engine_manifest()
    assert C.config_hash(base) != C.config_hash(changed)
    assert digest(C.setup_identity(base, engine, "s")) != digest(C.setup_identity(changed, engine, "s"))


# ----------------------------------------------------------------- inventory

def _fixture_config(full_config):
    expected = json.loads((FIXTURES / "inventory-3civ.json").read_text())
    raw = copy.deepcopy(full_config)
    raw["runId"] = "fixture-3civ"
    raw["selection"] = expected["selection"]
    return C.validate(raw), expected


def test_inventory_is_deterministic_and_matches_fixture(full_config):
    cfg, expected = _fixture_config(full_config)
    inputs = load_inputs(cfg)
    first = I.build(cfg, inputs["bundle"], inputs["scenarioSet"], inputs["orientation"], inputs["setupHash"])
    second = I.build(cfg, inputs["bundle"], inputs["scenarioSet"], inputs["orientation"], inputs["setupHash"])
    assert first == second
    assert inputs["setupHash"] == expected["setupHash"]
    assert first["summary"] == expected["summary"]
    assert first["jobs"][:3] == expected["firstJobs"]
    assert first["identity"] == expected["identity"]
    for job in first["jobs"]:
        assert job["contextHash"] == digest({"profiles": job["profileHashes"], "counts": job["counts"],
                                             "scenarioHash": job["scenarioHash"], "family": job["family"],
                                             "engineFamily": job["engineFamily"],
                                             "weightedCosts": job["weightedCosts"], "policy": job["policy"]})
        assert set(job["profileHashes"]) == set(job["pairKey"].split("|"))


def test_inventory_selection_and_orientation(full_config, bundle, tmp_path):
    cfg, _ = _fixture_config(full_config)
    inputs = load_inputs(cfg)
    scen = inputs["scenarioSet"]
    oriented = I.build(cfg, bundle, scen, inputs["orientation"])
    flat = I.build(cfg, bundle, scen, None)
    assert {j["pairKey"] for j in oriented["jobs"]} == {j["pairKey"] for j in flat["jobs"]}
    assert all(j["profileHashes"] == sorted(j["profileHashes"]) for j in flat["jobs"])
    # one civ against everyone: each of its variants meets every variant of the 55 other civs
    one = copy.deepcopy(cfg)
    one["selection"] = {**cfg["selection"], "civilizations": ["Franks"], "against": "*"}
    franks = sum(v["civilization"] == "Franks" for v in bundle["variants"])
    r = I.build(one, bundle, scen, None)
    assert r["summary"]["cells"] == franks * (555 - franks)
    # orientation tables round-trip
    table = I.orientation_table({j["pairKey"]: j["profileHashes"] for j in oriented["jobs"]}, {"test": True})
    B.write_json_gz(table, tmp_path / "o.json.gz")
    again = I.build(cfg, bundle, scen, I.load_orientation(tmp_path / "o.json.gz", table["tableHash"]))
    assert again["jobs"] == oriented["jobs"]


def test_reference_db_export_roster_rule(tmp_path, bundle):
    """export_from_reference_db on a tiny DB with the reference-DB schema."""
    db = tmp_path / "ref.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE ref_units (id INTEGER PRIMARY KEY, civ_name TEXT, unit_slug TEXT, unit_name TEXT,
            unit_type TEXT, age TEXT, final_cost_food REAL, final_cost_wood REAL, final_cost_gold REAL);
        CREATE TABLE ref_unit_mechanics (ref_unit_id INTEGER, mode TEXT, is_default INTEGER, schema_version INTEGER,
            mechanics_json TEXT, mechanics_hash TEXT, source_build TEXT);""")
    picks = [v for v in bundle["variants"] if v["civilization"] in ("Franks", "Britons")]
    for i, v in enumerate(picks, 1):
        c = v["referencePurchaseCost"]
        conn.execute("INSERT INTO ref_units VALUES (?,?,?,?,?,?,?,?,?)",
                     (i, v["civilization"], v["slug"], v["name"], "land", "Imperial", c["food"], c["wood"], c["gold"]))
        conn.execute("INSERT INTO ref_unit_mechanics VALUES (?,?,?,?,?,?,?)",
                     (i, v["mode"], 1, 1, json.dumps(v["mechanics"]), v["storedMechanicsHash"], v["sourceBuild"]))
    conn.execute("INSERT INTO ref_units VALUES (999,'Franks','galleon','Galleon','naval','Imperial',0,315,0)")
    conn.commit()
    conn.close()
    out = B.export_from_reference_db(db, game_build="test")
    assert [v["key"] for v in out["variants"]] == sorted(v["key"] for v in picks)
    by_key = {v["key"]: v for v in picks}
    for v in out["variants"]:
        assert v["profileHash"] == by_key[v["key"]]["profileHash"]
        assert v["group"] == by_key[v["key"]]["group"]
    assert [e["slug"] for e in out["roster"]["excluded"]] == ["galleon"]
    assert B.bundle_hash(out) == out["bundleHash"]
    B.write_json_gz(out, tmp_path / "b.json.gz")
    assert B.load_bundle(tmp_path / "b.json.gz")["bundleHash"] == out["bundleHash"]


# -------------------------------------------------------------------- engine

def test_engine_files_match_engine_json():
    report = E.verify_engine()
    assert report["ok"], report["problems"]
    assert report["files"] == 62 and report["bytes"] == 1_049_439
    manifest = E.load_engine_manifest()
    assert manifest["source"]["commit"].startswith("6c3049dfd")
    assert manifest["source"]["campaignHash"].startswith("d6c03bd7")
    assert manifest["node"]["pinned"] == "v24.19.0"
    assert {v["version"] for v in manifest["node"]["verified"]} >= {"v24.22.1"}
    assert all(v["identical"] == v["seeds"] >= 50 for v in manifest["node"]["verified"])


def test_engine_tampering_is_detected(tmp_path):
    root = tmp_path / "engine"
    shutil.copytree(E.engine_dir(), root)
    target = root / "aoe2x/js_simulation/src/combat/world.js"
    target.write_bytes(target.read_bytes() + b"\n")
    (root / "aoe2x/js_simulation/src/extra.js").write_text("// not pinned\n")
    report = E.verify_engine(root=root)
    assert not report["ok"]
    assert any("world.js" in p for p in report["problems"])
    assert any("unlisted file aoe2x/js_simulation/src/extra.js" == p for p in report["problems"])


def test_pinned_engine_is_outside_the_live_engine_and_backend_bundle():
    text = (REPO_ROOT / "scripts/migration/prepare_release.py").read_text()
    assert "aoe2x/matchups" not in text
    live = REPO_ROOT / "aoe2x/js_simulation/src"
    assert not E.engine_dir().resolve().is_relative_to(live.resolve())


# ------------------------------------------------------------- RB-dependent

def test_rb_commands_skip_without_the_research_branch():
    for command in (["replay-check"], ["import-2026", "--check"], ["check-inventory-2026"], ["import-results"]):
        out = subprocess.run([sys.executable, "-m", "aoe2x.matchups", "--rb-ref", "refs/heads/no-such-branch-xyz",
                              *command], cwd=REPO_ROOT, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        assert "skipped: research branch" in out.stderr
    out = subprocess.run([sys.executable, "-m", "aoe2x.matchups", "--rb-ref", "refs/heads/no-such-branch-xyz",
                          "--require-rb", "import-results"], cwd=REPO_ROOT, capture_output=True, text=True)
    assert out.returncode == 3
