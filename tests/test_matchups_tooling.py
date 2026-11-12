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


# =================================================================== step 3
# Runner, sampling, journals, lock, state, export: fast, no RB, no Node
# (a scripted in-process backend stands in for run-battles.mjs --serve).

import gzip
import os
import signal as _signal

from aoe2x.matchups import export as X
from aoe2x.matchups import journal as J
from aoe2x.matchups import runner as RN
from aoe2x.matchups import sampling as SP
from aoe2x.matchups import status as ST
from aoe2x.matchups.canonical import sha256_bytes

SAMPLING_CASES = json.loads((FIXTURES / "sampling-2026.json").read_text())["cases"]


def _policy(name):
    return SP.Policy({"policy": name, "initialSeeds": [0, 1, 2], "extraSeedsOnMixedWinners": [3, 4, 5, 6, 7, 8, 9],
                      "singleSeedMinimumWinnerHpFraction": 0.25})


@pytest.mark.parametrize("case", SAMPLING_CASES, ids=[c["name"] for c in SAMPLING_CASES])
def test_sampling_reproduces_2026_seed_sets(case):
    """Driving the policy seed by seed from nothing reaches exactly the archived seed set,
    decision and classification (RB forecast/mismatch reviews)."""
    policy, job, prior = _policy(case["policy"]), case["job"], case["prior"]
    by_seed = {s["seed"]: s for s in case["seeds"]}
    rows = []
    while True:
        needed = policy.decision(job, rows, prior)["requiredSeeds"]
        if not needed:
            break
        rows.extend(by_seed[s] for s in needed)  # a seed the archive lacks would raise KeyError
    assert [r["seed"] for r in rows] == sorted(by_seed)
    assert policy.outcome(job, rows, prior) == case["outcome"]
    if case["samplingDecision"] is not None:
        assert policy.decision(job, rows, prior) == case["samplingDecision"]


@pytest.mark.parametrize("case", [c for c in SAMPLING_CASES if len(c["seeds"]) == 1], ids=lambda c: c["name"])
def test_one_seed_shortcut_needs_an_agreeing_prior(case):
    policy, job = _policy("one-three-ten"), case["job"]
    first = case["seeds"][:1]
    assert policy.decision(job, first, case["prior"])["evidenceLevel"] == SP.SINGLE
    for prior in (None, [], ["a_win" if case["outcome"] == "b_win" else "b_win"], ["close_uncertain"],
                  [case["outcome"], "close_uncertain"]):
        d = policy.decision(job, first, prior)
        assert d["evidenceLevel"] == SP.MULTI and d["requiredSeeds"] == [1, 2], prior
    # a context without any prior may start its three initial seeds at once
    assert policy.dispatchable(job, [], None) == [0, 1, 2]
    assert policy.dispatchable(job, [], case["prior"]) == [0]
    assert _policy("three-then-ten").decision(job, first, case["prior"])["requiredSeeds"] == [1, 2]


def test_terminal_margin_and_classification_edges():
    base = {"seed": 0, "winnerOwner": 2, "unitStartingHp": 100, "opponentStartingHp": 80, "unitRemainingHp": 25,
            "opponentRemainingHp": 0, "unitSurvivors": 3, "opponentSurvivors": 0}
    assert SP.terminal_margin(base) == 0.25
    for change in ({"opponentSurvivors": 1}, {"opponentRemainingHp": 1}, {"unitSurvivors": 0}, {"unitRemainingHp": 0},
                   {"unitRemainingHp": 101}, {"winnerOwner": None}, {"unitStartingHp": 0}):
        assert SP.terminal_margin({**base, **change}) is None, change
    job = {"pairKey": "a|b", "profileHashes": ["b", "a"]}
    assert SP.physical_outcome(job, 2) == "b_win" and SP.physical_outcome(job, 3) == "a_win"
    assert SP.classify(job, [{"winnerOwner": None}] * 3) == "close_uncertain"  # unanimous draws
    assert SP.classify(job, [{"winnerOwner": 3}, {"winnerOwner": 3}]) == "a_win"
    with pytest.raises(ValueError, match="duplicate seed"):
        _policy("three-then-ten").decision(job, [base, base], None)
    assert SP.policy_name("distinct-seeds-1-3-10") == "one-three-ten"


# ------------------------------------------------------------- journal/lock

def test_journal_repairs_only_a_torn_trailing_line(tmp_path):
    path = tmp_path / "runs.jsonl"
    j = J.Journal(path)
    j.append({"a": 1})
    j.append({"a": 2})
    j.close()
    good = path.read_bytes()
    path.write_bytes(good + b'{"a": 3, "tor')
    report = J.repair_journal(path)
    assert report["repaired"] and report["lines"] == 2 and path.read_bytes() == good
    path.write_bytes(good + b'{"a": \n')
    assert J.repair_journal(path)["reason"] == "unparsable trailing line" and path.read_bytes() == good
    assert J.repair_journal(path) == {"repaired": False, "lines": 2}
    path.write_bytes(b'{"a": 1}\nnot json\n{"a": 3}\n')
    assert not J.repair_journal(path)["repaired"]
    with pytest.raises(J.IntegrityError, match="unparsable journal line"):
        J.read_journal(path)
    path.write_bytes(b'{"only": "tor')
    assert J.repair_journal(path)["lines"] == 0 and path.read_bytes() == b""


def test_atomic_json_write(tmp_path):
    J.write_json_atomic(tmp_path / "s.json", {"x": 1})
    J.write_json_atomic(tmp_path / "s.json", {"x": 2})
    assert J.read_json(tmp_path / "s.json") == {"x": 2}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["s.json"]


def _dead_pid():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def test_runner_lock_live_stale_and_recycled(tmp_path):
    path = tmp_path / ".runner.lock"
    lock = J.RunnerLock(path).acquire()
    with pytest.raises(J.LockBusy):
        J.RunnerLock(path).acquire()
    with pytest.raises(J.LockBusy):
        J.RunnerLock(path).clear_stale()
    lock.release()
    assert not path.exists()
    # stale: dead owner
    path.write_text(json.dumps({"pid": _dead_pid(), "startTime": "1", "host": os.uname().nodename}))
    second = J.RunnerLock(path).acquire()
    assert second.cleared and second.held
    second.release()
    # recycled PID: our own PID but another start time is not a live owner
    path.write_text(json.dumps({"pid": os.getpid(), "startTime": "-1", "host": os.uname().nodename}))
    assert J.RunnerLock(path).clear_stale()["cleared"]
    assert J.RunnerLock(path).clear_stale() == {"cleared": False, "reason": "no lock"}


# ---------------------------------------------------------- runner (fake)

class FakeBackend:
    """In-process stand-in for ``run-battles.mjs --serve``: deterministic results from (context, seed)."""

    def __init__(self, script):
        self.script = script  # (job_id, seed, limit, payload) -> result dict | failure dict
        self.replies = []
        self.submitted = []

    def start(self):
        manifest = E.load_engine_manifest()
        return {"engineId": manifest["engineId"], "filesDigest": manifest["filesDigest"], "node": {"version": "vfake"}}

    def submit(self, request):
        self.submitted.append(request)
        job_id, seed = request["payload"]["jobId"], request["payload"]["seed"]
        out = self.script(job_id, seed, request["limitSeconds"], request["payload"])
        if "outcome" in out:
            self.replies.insert(0, {"key": request["key"], "ok": True, "result": out, "startedAt": "t", "wallSeconds": 0.5})
        else:
            self.replies.insert(0, {"key": request["key"], "ok": False, "startedAt": "t", "wallSeconds": request["limitSeconds"], **out})

    def get(self, timeout):
        return self.replies.pop() if self.replies else None

    def stop(self):
        pass

    kill = stop


def fake_result(job_id, seed, *_):
    h = int(digest([job_id, seed])[:8], 16)
    mixed = int(digest(job_id)[:2], 16) % 3 == 0  # a third of the contexts get mixed winners
    winner = (2 if h % 2 else 3) if mixed else (2 if int(digest(job_id)[2:4], 16) % 2 else 3)
    loser = 5 - winner
    return {"outcome": "win", "winnerOwner": winner, "ticks": 1000 + h % 5000,
            "startingHpByOwner": {"2": 1000, "3": 900},
            "remainingByOwner": {str(winner): {"hp": 300 + h % 300, "units": 1 + h % 9}, str(loser): {"hp": 0, "units": 0}},
            "finalStateHash": digest(["f", job_id, seed]), "eventLogHash": digest(["e", job_id, seed])}


@pytest.fixture(scope="module")
def small_inventory(full_config, bundle):
    cfg, _ = _fixture_config(full_config)
    inputs = load_inputs(cfg)
    jobs = I.build(cfg, inputs["bundle"], inputs["scenarioSet"], inputs["orientation"], inputs["setupHash"])["jobs"]
    return [j["pairKey"] for j in jobs[:12]], inputs["setupHash"]


def _small_config(full_config, tmp_path, pair_keys, **sampling):
    raw = copy.deepcopy(full_config)
    raw["runId"] = "unit-small"
    ctx = (json.dumps(sorted(pair_keys)) + "\n").encode()
    (tmp_path / "contexts.json").write_bytes(ctx)
    raw["selection"] = {"mode": "full", "civilizations": None, "units": None, "against": "*",
                        "contexts": {"file": str(tmp_path / "contexts.json"), "sha256": sha256_bytes(ctx)}}
    raw["sampling"].update(sampling)
    raw["execution"]["workers"] = 3
    raw["execution"]["phaseContexts"] = 5
    raw["output"] = {"records": str(tmp_path / "records")}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw))
    return C.load(path)


def _runner(cfg, script=fake_result, records=None, **kw):
    run = RN.Run(cfg, records=records)
    backend = FakeBackend(script)
    return RN.Runner(run, backend_factory=lambda: backend, log=lambda m: None, **kw), backend


def _journal_content(records):
    return sorted((RN.content(r) for r in J.read_journal(records / "runs.jsonl")),
                  key=lambda r: (r["matchupId"], r["seed"]))


def test_runner_completes_and_writes_records(full_config, tmp_path, small_inventory):
    cfg = _small_config(full_config, tmp_path, small_inventory[0])
    runner, backend = _runner(cfg)
    assert runner.execute() == RN.EXIT_DONE
    R = tmp_path / "records"
    state = J.read_json(R / "state.json")
    assert state["status"] == "complete" and state["pid"] is None
    assert state["contexts"] == {"total": 12, "complete": 12, "reviewed": 12, "reused": 0, "blocked": 0,
                                 "remaining": 0, "active": 0}
    rows = J.read_journal(R / "runs.jsonl")
    assert state["seeds"]["saved"] == len(rows) == len(backend.submitted)
    assert len({(r["matchupId"], r["seed"]) for r in rows}) == len(rows)
    assert {len([r for r in rows if r["matchupId"] == j]) for j in {r["matchupId"] for r in rows}} <= {3, 10}
    for field in ("campaignHash", "matchupId", "pairKey", "contextHash", "seed", "wallSeconds", "outcome", "winnerOwner",
                  "unitStartingHp", "opponentRemainingHp", "unitSurvivors", "ticks", "simulationSeconds",
                  "finalStateHash", "eventLogHash", "physicsVersion", "executionVersion", "engineId", "nodeVersion"):
        assert field in rows[0]
    assert rows[0]["nodeVersion"] == "vfake" and rows[0]["engineId"] == "frozen-civ-matchups-v3"
    reviews = sorted((R / "pair-reviews").glob("*.json"))
    assert len(reviews) == 12
    review = json.loads(reviews[0].read_text())
    assert review["reviewHash"] == digest({k: v for k, v in review.items() if k != "reviewHash"})
    assert {"context", "contextHash", "pairKey", "jobId", "outcome", "seedResults", "physicsVersion",
            "validationMode", "evidenceLevel", "samplingDecision"} <= set(review)
    assert sorted(p.name for p in (R / "reviews").glob("*.json")) == ["001.json", "002.json", "003.json"]
    assert J.read_json(R / "reviews/003.json")["plannedJobs"] == 2
    assert not (R / ".runner.lock").exists()
    # a second run is a no-op: nothing is re-run
    again, backend2 = _runner(cfg)
    assert again.execute() == RN.EXIT_DONE and backend2.submitted == []


def test_runner_resume_after_interruptions_equals_uninterrupted(full_config, tmp_path, small_inventory):
    cfg = _small_config(full_config, tmp_path, small_inventory[0])
    reference, _ = _runner(cfg, records=tmp_path / "reference")
    assert reference.execute() == RN.EXIT_DONE
    R = tmp_path / "records"
    for stop_after in (2, 7, 5, 11):
        count = [0]

        def script(job_id, seed, limit, payload, count=count, stop_after=stop_after):
            count[0] += 1
            if count[0] == stop_after:
                runner.stopping, runner.stop_reason = True, "test kill"
            return fake_result(job_id, seed)
        runner, _ = _runner(cfg, script)
        code = runner.execute()
        if code == RN.EXIT_DONE:
            break
        assert code == RN.EXIT_STOPPED and J.read_json(R / "state.json")["status"] == "interrupted"
        # simulate a kill in the middle of a write: a torn trailing line
        with open(R / "runs.jsonl", "ab") as f:
            f.write(b'{"campaignHash": "torn')
    final, _ = _runner(cfg)
    assert final.execute() == RN.EXIT_DONE
    assert _journal_content(R) == _journal_content(tmp_path / "reference")
    state = J.read_json(R / "state.json")
    assert state["seeds"]["saved"] == len(_journal_content(R))
    assert state["contexts"]["reviewed"] == 12
    sessions = J.read_journal(R / "sessions.jsonl")
    assert any(s.get("journalRepair") for s in sessions if s["event"] == "start")
    # same journals -> byte-identical export, interrupted or not
    a = X.build(RN.Run(cfg, records=R))[1]
    b = X.build(RN.Run(cfg, records=tmp_path / "reference"))[1]
    assert a == b


def test_runner_refuses_duplicate_seed_lines_and_foreign_journals(full_config, tmp_path, small_inventory):
    cfg = _small_config(full_config, tmp_path, small_inventory[0][:2])
    runner, _ = _runner(cfg)
    assert runner.execute() == RN.EXIT_DONE
    R = tmp_path / "records"
    lines = (R / "runs.jsonl").read_bytes().splitlines(keepends=True)
    (R / "runs.jsonl").write_bytes(b"".join(lines) + lines[0])
    runner, _ = _runner(cfg)
    assert runner.execute() == RN.EXIT_INTEGRITY
    (R / "runs.jsonl").write_bytes(b"".join(lines).replace(b'"campaignHash":"', b'"campaignHash":"x', 1))
    runner, _ = _runner(cfg)
    assert runner.execute() == RN.EXIT_INTEGRITY


def test_runner_lock_blocks_second_runner(full_config, tmp_path, small_inventory):
    cfg = _small_config(full_config, tmp_path, small_inventory[0][:2])
    holder = J.RunnerLock(tmp_path / "records" / ".runner.lock").acquire()
    runner, backend = _runner(cfg)
    assert runner.execute() == RN.EXIT_LOCKED and backend.submitted == []
    holder.release()
    runner, _ = _runner(cfg)
    assert runner.execute() == RN.EXIT_DONE


def test_timeouts_escalate_then_block(full_config, tmp_path, small_inventory):
    keys = small_inventory[0][:4]
    cfg = _small_config(full_config, tmp_path, keys)
    stuck = RN.Run(cfg).prepare(build=True).jobs[1]["id"]

    def script(job_id, seed, limit, payload):
        if job_id == stuck and seed == 1:
            return {"watchdog": True, "lastProgress": {"tick": int(limit * 60)}}
        return fake_result(job_id, seed)
    runner, backend = _runner(cfg, script)
    assert runner.execute() == RN.EXIT_DONE
    R = tmp_path / "records"
    attempts = J.read_journal(R / "attempts.jsonl")
    assert [(a["matchupId"], a["seed"], a["limitSeconds"], a["exhausted"]) for a in attempts] == \
        [(stuck, 1, 180, False), (stuck, 1, 600, False), (stuck, 1, 1800, False), (stuck, 1, 3600, True)]
    state = J.read_json(R / "state.json")
    assert state["status"] == "complete_with_blocked" and state["blockedJobs"] == [stuck]
    assert state["contexts"]["reviewed"] == 3 and state["contexts"]["blocked"] == 1
    assert not (R / "pair-reviews" / f"{stuck}.json").exists()
    report = ST.report(R)
    assert [b["jobId"] for b in report["blocked"]] == [stuck] and "BLOCKED " + stuck in ST.render(report)
    # restart: the blocked context is not retried ...
    again, backend2 = _runner(cfg, script)
    assert again.execute() == RN.EXIT_DONE and backend2.submitted == []
    # ... unless asked, and then it gets a fresh set of steps
    retry, backend3 = _runner(cfg, fake_result, retry_blocked=True)
    assert retry.execute() == RN.EXIT_DONE
    assert J.read_json(R / "state.json")["status"] == "complete"
    assert [r["limitSeconds"] for r in backend3.submitted][:1] == [180]
    assert X.build(RN.Run(cfg, records=R))[0]["counts"]["blocked"] == 0


def test_one_three_ten_priors_and_reuse(full_config, tmp_path, small_inventory):
    keys, setup_hash = small_inventory
    cfg0 = _small_config(full_config, tmp_path, keys)
    jobs = RN.Run(cfg0).prepare(build=True).jobs
    # baseline index: the first 4 contexts have reusable results, 4 more only a prior outcome
    index = []
    for i, j in enumerate(jobs[:8]):
        winner = 2 if int(digest(j["id"])[2:4], 16) % 2 else 3
        outcome = SP.physical_outcome(j, winner)
        row = {"pairKey": j["pairKey"], "outcome": outcome, "evidenceType": "observed", "source": "test",
               "context": {"profiles": j["profileHashes"]}, "contextHash": j["contextHash"], "seeds": [],
               "reusable": i < 4}
        if i < 4:
            row["resultKey"] = j["resultKey"]
        index.append(row)
    data = gzip.compress("".join(json.dumps(r) + "\n" for r in index).encode(), mtime=0)
    (tmp_path / "index.jsonl.gz").write_bytes(data)
    raw = json.loads((tmp_path / "config.json").read_text())
    raw["selection"]["baselineResults"] = {"index": str(tmp_path / "index.jsonl.gz"), "sha256": sha256_bytes(data)}
    raw["sampling"].update(policy="one-three-ten", forecastSource="baseline-outcome")
    (tmp_path / "config.json").write_text(json.dumps(raw))
    cfg = C.load(tmp_path / "config.json")
    runner, backend = _runner(cfg)
    assert runner.execute() == RN.EXIT_DONE
    R = tmp_path / "records"
    reuse = J.read_json(R / "reuse.json")
    assert reuse["reused"] == 4 and sorted(c[0] for c in reuse["contexts"]) == sorted(j["id"] for j in jobs[:4])
    submitted = {r["payload"]["jobId"] for r in backend.submitted}
    assert submitted == {j["id"] for j in jobs[4:]}
    reviews = {p.stem: json.loads(p.read_text()) for p in (R / "pair-reviews").glob("*.json")}
    for j in jobs[4:]:
        r = reviews[j["id"]]
        if j in jobs[4:8] and r["seedCount"] == 1:
            assert r["evidenceLevel"] == SP.SINGLE and r["priorOutcomes"] == [r["outcome"]]
        if j in jobs[8:]:
            assert r["priorOutcomes"] is None and r["seedCount"] >= 3  # no prior: never one seed
    assert any(r["seedCount"] == 1 for r in reviews.values())
    state = J.read_json(R / "state.json")
    assert state["contexts"]["reused"] == 4 and state["contexts"]["complete"] == 12
    manifest, files = X.build(RN.Run(cfg, records=R))
    assert manifest["counts"]["reused"] == 4 and manifest["counts"]["reviewed"] == 8 and manifest["complete"]
    # --force re-runs the reusable contexts too (fresh records)
    forced, backend = _runner(cfg, records=tmp_path / "forced")
    forced.run.force = True
    assert forced.execute() == RN.EXIT_DONE
    assert {r["payload"]["jobId"] for r in backend.submitted} == {j["id"] for j in jobs}


def test_export_is_deterministic(full_config, tmp_path, small_inventory):
    cfg = _small_config(full_config, tmp_path, small_inventory[0][:6])
    runner, _ = _runner(cfg)
    assert runner.execute() == RN.EXIT_DONE
    run = RN.Run(cfg)
    first = X.write(run, tmp_path / "e1")
    second = X.write(RN.Run(cfg), tmp_path / "e2")
    assert first == second
    for name in ("manifest.json", "results.jsonl.gz", "reused.jsonl.gz", "blocked.jsonl.gz"):
        assert (tmp_path / "e1" / name).read_bytes() == (tmp_path / "e2" / name).read_bytes()
    rows = [json.loads(l) for l in gzip.decompress((tmp_path / "e1/results.jsonl.gz").read_bytes()).decode().splitlines()]
    assert len(rows) == 6 and rows == sorted(rows, key=lambda r: r["pairKey"])
    assert all(len(s) == len(X.SEED_FIELDS) for r in rows for s in r["seeds"])
    assert first["journal"]["runsSha256"] == sha256_bytes((tmp_path / "records/runs.jsonl").read_bytes())
    # a tampered review is refused
    review = sorted((tmp_path / "records/pair-reviews").glob("*.json"))[0]
    body = json.loads(review.read_text())
    body["outcome"] = "close_uncertain"
    review.write_text(json.dumps(body))
    with pytest.raises(RN.RunError, match="failed verification"):
        X.build(RN.Run(cfg))


def test_runner_stops_on_sigterm_and_stop_file(full_config, tmp_path, small_inventory):
    cfg = _small_config(full_config, tmp_path, small_inventory[0])

    def script(job_id, seed, limit, payload):
        if len(backend.submitted) == 4:
            os.kill(os.getpid(), _signal.SIGTERM)
        return fake_result(job_id, seed)
    runner, backend = _runner(cfg, script)
    assert runner.execute() == RN.EXIT_STOPPED
    state = J.read_json(tmp_path / "records/state.json")
    assert state["status"] == "interrupted" and state["stopReason"] == "SIGTERM"
    (tmp_path / "records/STOP").write_text("")
    runner, backend = _runner(cfg)
    assert runner.execute() == RN.EXIT_STOPPED and backend.submitted == []
    (tmp_path / "records/STOP").unlink()
    runner, backend = _runner(cfg)
    assert runner.execute() == RN.EXIT_DONE


def test_runner_and_supervisor_commands_exist():
    out = subprocess.run([sys.executable, "-m", "aoe2x.matchups", "--help"], cwd=REPO_ROOT, capture_output=True, text=True)
    for command in ("run", "supervise", "status", "unlock", "export", "reproduce-2026"):
        assert command in out.stdout
