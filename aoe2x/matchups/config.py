"""Run-config files (``aoe2-matchup-run/v1``): one declarative JSON per run.

Everything that changes a battle is in the config; its canonical hash is the
run's identity, and the battle/engine part is hashed into every context's
``setupHash`` so changed conditions never reuse old results by accident.
Schema: RERUN_SYSTEM_PROPOSAL.md section 4, with these concrete choices:

* ``game.bundle`` names a committed mechanics bundle (+ its hash), or
  ``game.referenceDb`` names a reference DB that is exported to a bundle at
  freeze time (a future patch/DLC). Runs never read the live reference DB
  implicitly.
* ``battle.orientation`` is ``{"rule": "sorted-profile-hash"}`` (fresh runs)
  or ``{"rule": "table", "table": <path>, "tableHash": <hash>}`` (reuse a
  baseline's physical orientation, e.g. the 2026 adaptive inventory).
* ``engine.nodeVersionPolicy`` is ``exact`` | ``verified`` | ``warn``.
* ``output.records`` defaults to ``${MATCHUP_RUNS_STORE}/<runId>``; it must be
  outside the repository unless ``output.allowInsideRepo`` is true.

Optional fields added for the runner (build step 3). They have no default, so
configs that do not use them keep their earlier ``config_hash``:

* ``selection.contexts`` ``{"file", "sha256"}``: restrict the run to these
  ``pairKey``s (a JSON list, or JSONL[.gz] rows with ``pairKey``), e.g. a
  reproduction sample.
* ``selection.baselineResults`` ``{"index", "sha256"}``: a result index
  (``import-results`` output). Inventory contexts whose ``resultKey`` has a
  reusable result there are not run but recorded as reused, unless
  ``selection.rerunReusable`` is true (or ``run --force``). With
  ``sampling.forecastSource: "baseline-outcome"`` the index row of the same
  context (``contextHash``) is the prior for the one-seed shortcut.
* ``sampling.policy`` also accepts ``three-then-ten`` / ``one-three-ten``
  (the names used in the runner docs; same rules as ``distinct-seeds-3-10`` /
  ``distinct-seeds-1-3-10``).
* ``sampling.forecastSource: "priors-file"`` with ``sampling.priors``
  ``{"file", "sha256"}``: JSONL[.gz] rows ``{"contextHash"|"pairKey", "outcomes": [...]}``.
* ``execution.diagnostics``: ``"after-first-timeout"`` (default behaviour),
  ``"always"`` or ``"never"`` - when to write the 30-second diagnostic
  progress snapshots (never results).
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path

from aoe2x.matchups.battle import DEFAULT_CAP, DEFAULT_WEIGHTS
from aoe2x.matchups.canonical import digest
from aoe2x.matchups.paths import REPO_ROOT, runs_store

SCHEMA = "aoe2-matchup-run/v1"
SAMPLING_POLICIES = ("distinct-seeds-1-3-10", "distinct-seeds-3-10", "one-three-ten", "three-then-ten")
FORECAST_SOURCES = ("baseline-outcome", "none", "priors-file")
DIAGNOSTICS = ("after-first-timeout", "always", "never")
# Optional fields: validated when present, never filled in (keeps older config hashes stable).
OPTIONAL = {"selection": {"contexts", "baselineResults", "rerunReusable"},
            "sampling": {"priors"}, "execution": {"diagnostics"}}
NODE_POLICIES = ("exact", "verified", "warn")
ORIENTATION_RULES = ("sorted-profile-hash", "table")

DEFAULTS = {
    "selection": {"mode": "full", "civilizations": None, "units": None, "against": "*",
                  "excludeUnits": [], "baselineResults": None},
    "battle": {"armyCap": DEFAULT_CAP, "resourceWeights": dict(DEFAULT_WEIGHTS),
               "costBasis": "mechanics.cost", "bufferUnits": 0, "disableKiting": True,
               "disableAiOrders": True, "preserveOwnerOrientation": True,
               "orientation": {"rule": "sorted-profile-hash"},
               "scenarioSet": None, "scenarioSetHash": None},
    "engine": {"id": "frozen-civ-matchups-v3", "nodeVersionPolicy": "verified", "node": None,
               "maxSimulationTicks": "unbounded", "wallTimeoutSteps": [180, 600, 1800, 3600],
               "environment": {}},
    "sampling": {"policy": "distinct-seeds-1-3-10", "forecastSource": "baseline-outcome",
                 "singleSeedMinimumWinnerHpFraction": 0.25, "initialSeeds": [0, 1, 2],
                 "extraSeedsOnMixedWinners": [3, 4, 5, 6, 7, 8, 9], "sameSeedReplay": "sample:50"},
    "execution": {"workers": 4, "phaseContexts": 128, "maxOldSpaceMb": 3072},
    "output": {"records": "${MATCHUP_RUNS_STORE}/${runId}", "allowInsideRepo": False},
}
TOP_LEVEL = {"schema", "runId", "description", "game", "roster", "selection", "battle", "engine",
             "sampling", "execution", "output"}


class ConfigError(ValueError):
    pass


def _merge(defaults: dict, value: dict | None, where: str) -> dict:
    value = value or {}
    unknown = set(value) - set(defaults) - OPTIONAL.get(where, set())
    if unknown:
        raise ConfigError(f"{where}: unknown field(s) {sorted(unknown)}")
    merged = copy.deepcopy(defaults)
    merged.update(copy.deepcopy(value))
    return merged


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise ConfigError(message)


def resolve_path(value: str, base: Path, run_id: str = "") -> Path:
    """Expand ``${MATCHUP_RUNS_STORE}``/``${runId}``/env vars; relative paths are repo-relative."""
    text = value.replace("${MATCHUP_RUNS_STORE}", str(runs_store())).replace("${runId}", run_id)
    text = os.path.expandvars(os.path.expanduser(text))
    path = Path(text)
    return path if path.is_absolute() else (REPO_ROOT / path)


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def validate(raw: dict) -> dict:
    """Return a normalised config (defaults filled in) or raise ConfigError."""
    _require(isinstance(raw, dict), "config must be a JSON object")
    unknown = set(raw) - TOP_LEVEL
    _require(not unknown, f"unknown top-level field(s) {sorted(unknown)}")
    _require(raw.get("schema") == SCHEMA, f"schema must be {SCHEMA!r}")
    run_id = raw.get("runId")
    _require(isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", run_id or "") is not None,
             "runId must be 1-100 characters of letters, digits, '.', '_' or '-'")
    cfg = {"schema": SCHEMA, "runId": run_id, "description": raw.get("description", "")}

    game = raw.get("game") or {}
    _require(isinstance(game, dict), "game must be an object")
    _require(set(game) <= {"bundle", "bundleHash", "referenceDb", "referenceDbSha256", "gameBuild"},
             f"game: unknown field(s) {sorted(set(game) - {'bundle', 'bundleHash', 'referenceDb', 'referenceDbSha256', 'gameBuild'})}")
    _require(bool(game.get("bundle")) != bool(game.get("referenceDb")),
             "game needs exactly one of 'bundle' or 'referenceDb'")
    if game.get("bundle"):
        _require(isinstance(game.get("bundleHash"), str) and len(game["bundleHash"]) >= 8,
                 "game.bundleHash (at least 8 hex characters) is required with game.bundle")
    else:
        _require(isinstance(game.get("referenceDbSha256"), str) and len(game["referenceDbSha256"]) == 64,
                 "game.referenceDbSha256 (64 hex) is required with game.referenceDb")
        _require(isinstance(game.get("gameBuild"), str) and game["gameBuild"], "game.gameBuild is required")
    cfg["game"] = game

    roster = raw.get("roster")
    if roster is not None:
        _require(isinstance(roster, dict), "roster must be an object")
        _require(not game.get("bundle"), "roster rules apply only to game.referenceDb (a bundle already holds its roster)")
        _require(set(roster) <= {"rule", "groups", "extraLines", "excludeKeys", "requireModes"},
                 "roster: unknown field")
        _require(roster.get("rule", "ranking-roster-v1") == "ranking-roster-v1", "roster.rule must be ranking-roster-v1")
    cfg["roster"] = roster

    sel = _merge(DEFAULTS["selection"], raw.get("selection"), "selection")
    _require(sel["mode"] in ("full", "incremental"), "selection.mode must be 'full' or 'incremental'")
    for field in ("civilizations", "units"):
        _require(sel[field] is None or (isinstance(sel[field], list) and sel[field]
                                         and all(isinstance(x, str) for x in sel[field])),
                 f"selection.{field} must be null or a non-empty list of strings")
    against = sel["against"]
    _require(against == "*" or (isinstance(against, dict) and set(against) <= {"civilizations", "units"} and against),
             "selection.against must be '*' or {'civilizations': [...], 'units': [...]}")
    _require(isinstance(sel["excludeUnits"], list), "selection.excludeUnits must be a list")
    if sel["mode"] == "incremental":
        _require(bool(sel["baselineResults"]), "incremental selection needs selection.baselineResults")
    for field, key in (("contexts", "file"), ("baselineResults", "index")):
        ref = sel.get(field)
        if ref is not None:
            _require(isinstance(ref, dict) and set(ref) == {key, "sha256"} and isinstance(ref[key], str)
                     and isinstance(ref["sha256"], str) and len(ref["sha256"]) == 64,
                     f"selection.{field} must be {{'{key}': <path>, 'sha256': <64 hex>}}")
    if "rerunReusable" in sel:
        _require(isinstance(sel["rerunReusable"], bool), "selection.rerunReusable must be true or false")
    cfg["selection"] = sel

    battle = _merge(DEFAULTS["battle"], raw.get("battle"), "battle")
    _require(isinstance(battle["armyCap"], int) and not isinstance(battle["armyCap"], bool)
             and 1 <= battle["armyCap"] <= 27,
             "battle.armyCap must be an integer 1-27 (the recorded formations have 27 cells per side)")
    w = battle["resourceWeights"]
    _require(isinstance(w, dict) and set(w) == {"food", "wood", "gold"}
             and all(isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 for v in w.values()),
             "battle.resourceWeights must give positive food, wood and gold weights")
    _require(battle["costBasis"] == "mechanics.cost", "battle.costBasis must be 'mechanics.cost'")
    _require(battle["bufferUnits"] == 0, "battle.bufferUnits must be 0 (player-4 buffer armies are not supported)")
    for flag in ("disableKiting", "disableAiOrders", "preserveOwnerOrientation"):
        _require(isinstance(battle[flag], bool), f"battle.{flag} must be true or false")
    o = battle["orientation"]
    _require(isinstance(o, dict) and o.get("rule") in ORIENTATION_RULES,
             f"battle.orientation.rule must be one of {ORIENTATION_RULES}")
    if o["rule"] == "table":
        _require(isinstance(o.get("table"), str) and isinstance(o.get("tableHash"), str),
                 "battle.orientation 'table' needs 'table' and 'tableHash'")
    _require(isinstance(battle["scenarioSet"], str) and isinstance(battle["scenarioSetHash"], str)
             and len(battle["scenarioSetHash"]) >= 8,
             "battle.scenarioSet (path) and battle.scenarioSetHash are required")
    cfg["battle"] = battle

    engine = _merge(DEFAULTS["engine"], raw.get("engine"), "engine")
    _require(isinstance(engine["id"], str) and re.fullmatch(r"[a-z0-9][a-z0-9.+-]*", engine["id"]) is not None,
             "engine.id must name a directory under aoe2x/matchups/engines")
    _require(engine["nodeVersionPolicy"] in NODE_POLICIES, f"engine.nodeVersionPolicy must be one of {NODE_POLICIES}")
    _require(engine["maxSimulationTicks"] == "unbounded" or (isinstance(engine["maxSimulationTicks"], int)
                                                              and engine["maxSimulationTicks"] > 0),
             "engine.maxSimulationTicks must be 'unbounded' or a positive integer")
    steps = engine["wallTimeoutSteps"]
    _require(isinstance(steps, list) and steps and all(isinstance(s, (int, float)) and s > 0 for s in steps)
             and steps == sorted(steps), "engine.wallTimeoutSteps must be increasing positive seconds")
    env = engine["environment"]
    _require(isinstance(env, dict) and all(k.startswith("AOE2X_EXP_") and isinstance(v, str) for k, v in env.items()),
             "engine.environment may only hold AOE2X_EXP_* string values")
    cfg["engine"] = engine

    sampling = _merge(DEFAULTS["sampling"], raw.get("sampling"), "sampling")
    _require(sampling["policy"] in SAMPLING_POLICIES, f"sampling.policy must be one of {SAMPLING_POLICIES}")
    _require(sampling["forecastSource"] in FORECAST_SOURCES, f"sampling.forecastSource must be one of {FORECAST_SOURCES}")
    if sampling["forecastSource"] == "priors-file" or "priors" in sampling:
        ref = sampling.get("priors")
        _require(sampling["forecastSource"] == "priors-file" and isinstance(ref, dict)
                 and set(ref) == {"file", "sha256"} and isinstance(ref["file"], str)
                 and isinstance(ref["sha256"], str) and len(ref["sha256"]) == 64,
                 "sampling.priors {'file', 'sha256'} goes with forecastSource 'priors-file'")
    seeds = sampling["initialSeeds"] + sampling["extraSeedsOnMixedWinners"]
    _require(all(isinstance(s, int) and 0 <= s <= 0xFFFFFFFF for s in seeds) and len(set(seeds)) == len(seeds),
             "sampling seeds must be distinct uint32 values")
    _require(0 <= sampling["singleSeedMinimumWinnerHpFraction"] <= 1, "singleSeedMinimumWinnerHpFraction must be 0-1")
    _require(re.fullmatch(r"none|sample:\d+", str(sampling["sameSeedReplay"])) is not None,
             "sampling.sameSeedReplay must be 'none' or 'sample:N'")
    cfg["sampling"] = sampling

    execution = _merge(DEFAULTS["execution"], raw.get("execution"), "execution")
    _require(isinstance(execution["workers"], int) and execution["workers"] >= 1, "execution.workers must be >= 1")
    _require(isinstance(execution["phaseContexts"], int) and execution["phaseContexts"] >= 1, "execution.phaseContexts must be >= 1")
    _require(execution["maxOldSpaceMb"] is None or (isinstance(execution["maxOldSpaceMb"], int) and execution["maxOldSpaceMb"] >= 256),
             "execution.maxOldSpaceMb must be null or >= 256")
    if "diagnostics" in execution:
        _require(execution["diagnostics"] in DIAGNOSTICS, f"execution.diagnostics must be one of {DIAGNOSTICS}")
    cfg["execution"] = execution

    output = _merge(DEFAULTS["output"], raw.get("output"), "output")
    records = resolve_path(output["records"], REPO_ROOT, run_id)
    if not output["allowInsideRepo"]:
        _require(not _is_inside(records, REPO_ROOT),
                 f"output.records {records} is inside the repository; bulky run records stay out of git "
                 "(set output.allowInsideRepo only for tiny test runs)")
    cfg["output"] = output
    return cfg


def load(path: Path) -> dict:
    path = Path(path)
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise ConfigError(f"{path}: invalid JSON: {error}") from error
    return validate(raw)


def config_hash(cfg: dict) -> str:
    return digest(cfg)


def run_hash(cfg: dict) -> str:
    """The run's identity in its journals (``campaignHash``): every field that decides which
    battles run and how, i.e. the config without ``output`` (where records go) and
    ``execution`` (worker count, memory, diagnostics), which cannot change a result."""
    return digest({k: v for k, v in cfg.items() if k not in ("output", "execution", "description")})


def selection_hash(cfg: dict) -> str:
    """What decides the inventory besides the inputs (recorded in inventory-summary.json)."""
    sel = {k: v for k, v in cfg["selection"].items() if k not in ("baselineResults", "rerunReusable")}
    return digest({"selection": sel, "orientation": cfg["battle"]["orientation"]})


def setup_identity(cfg: dict, engine_manifest: dict, scenario_set_hash: str) -> dict:
    """What a stored result must share to be reused: battle rules + engine + scenarios."""
    b = cfg["battle"]
    return {"armyCap": b["armyCap"], "resourceWeights": b["resourceWeights"], "costBasis": b["costBasis"],
            "bufferUnits": b["bufferUnits"], "disableKiting": b["disableKiting"],
            "disableAiOrders": b["disableAiOrders"], "preserveOwnerOrientation": b["preserveOwnerOrientation"],
            "scenarioSetHash": scenario_set_hash, "engineId": engine_manifest["engineId"],
            "engineFilesDigest": engine_manifest["filesDigest"],
            "maxSimulationTicks": cfg["engine"]["maxSimulationTicks"],
            "environment": cfg["engine"]["environment"]}


def records_dir(cfg: dict) -> Path:
    return resolve_path(cfg["output"]["records"], REPO_ROOT, cfg["runId"])
